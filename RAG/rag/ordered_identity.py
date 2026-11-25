"""Verified identity matching shared by the medication-bag data paths."""
import re
from decimal import Decimal

from medication_identity import clean, dosage_form, license_key, present

PRIORITIES = ("trade_name", "strength", "manufacturer", "name_zh")
OPHTHALMIC_FORMS = {"眼用軟膏", "眼藥膏", "點眼膏劑", "eye ointment", "ophthalmic ointment"}


def identity_key(value):
    return "".join(clean(value).lower().split())


def _matches_name(observed, official, aliases):
    key = identity_key(observed)
    return bool(key) and key in {identity_key(official), *(identity_key(a) for a in aliases)}


def _strength(value):
    """Normalize one explicit strength without conflating mass and concentration."""
    units = {"mcg": ("mass", Decimal("0.001")), "ug": ("mass", Decimal("0.001")),
             "μg": ("mass", Decimal("0.001")), "微克": ("mass", Decimal("0.001")),
             "mg": ("mass", Decimal(1)), "毫克": ("mass", Decimal(1)),
             "g": ("mass", Decimal(1000)), "公克": ("mass", Decimal(1000)),
             "ml": ("volume", Decimal(1)), "毫升": ("volume", Decimal(1)),
             "l": ("volume", Decimal(1000)), "%": ("percent", Decimal(1))}
    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*(mcg|ug|μg|微克|mg|毫克|g|公克|%)"
        r"(?:\s*/\s*(\d+(?:\.\d+)?)?\s*(mg|毫克|g|公克|ml|毫升|l))?",
        clean(value),
    )
    if not match:
        return None
    amount, unit, denominator, denominator_unit = match.groups()
    dimension, scale = units[unit]
    quantity = Decimal(amount) * scale
    if not denominator_unit:
        return (dimension, quantity) if quantity > 0 else None
    divisor_dimension, divisor_scale = units[denominator_unit]
    divisor = Decimal(denominator or 1) * divisor_scale
    if dimension != "mass" or not divisor or not quantity:
        return None
    return (f"mass/{divisor_dimension}", quantity / divisor)


def _form(text):
    return ({"ophthalmic_ointment"}, set()) if clean(text) in OPHTHALMIC_FORMS else dosage_form(text)


def find_identity(cur, observed):
    """Require all four checks and a verified link to the exact leaflet version."""
    if observed.get("conflicting_fields"):
        return {"status": "not_found", "candidate_ids": []}
    cur.execute(
        """
        SELECT v.drug_id, v.source_id, v.license_no, m.name_zh, m.name_en,
               m.manufacturer, m.strength, m.dosage_form, m.package_size,
               COALESCE((
                   SELECT jsonb_object_agg(a.alias_type, a.names)
                   FROM (
                       SELECT alias_type, array_agg(alias_raw) AS names
                       FROM rag_v2.drug_aliases
                       WHERE license_no = m.license_no AND verified
                       GROUP BY alias_type
                   ) a
               ), '{}'::jsonb)
        FROM rag_v2.drug_master m
        JOIN rag_v2.leaflet_links l USING (license_no)
        JOIN rag_v2.current_leaflet_versions v ON v.drug_id = l.drug_id
             AND v.leaflet_version = l.leaflet_version
        WHERE l.verified
          AND (rag_v2.identity_key(m.name_en) = %s OR EXISTS (
              SELECT 1 FROM rag_v2.drug_aliases a
              WHERE a.license_no = m.license_no AND a.alias_type = 'trade_name'
                AND a.alias_norm = %s AND a.verified
          ))
        """,
        (identity_key(observed.get("trade_name")),) * 2,
    )
    return rank_candidates(observed, cur.fetchall())


def rank_candidates(observed, rows):
    """Only a unique full match can supply a leaflet. Partial hits are diagnostic."""
    actual_strength = _strength(observed.get("strength"))
    actual_form = _form(observed.get("dosage_form"))
    actual_package = clean(observed.get("package_size"))
    actual_license = license_key(observed.get("license_number"))
    full = []
    partial = []
    for drug_id, source_id, license_no, name_zh, name_en, manufacturer, strength, form, package, aliases in rows:
        expected_strength = _strength(strength)
        expected_form = _form(form)
        if actual_license and actual_license != license_key(license_no):
            continue
        if any(actual_form) and any(expected_form) and actual_form != expected_form:
            continue
        if present(actual_package) and present(package) and identity_key(actual_package) != identity_key(package):
            continue
        if actual_strength and expected_strength and actual_strength != expected_strength:
            continue
        checks = (
            _matches_name(observed.get("trade_name"), name_en, aliases.get("trade_name", [])),
            bool(actual_strength and expected_strength),
            _matches_name(observed.get("manufacturer"), manufacturer, aliases.get("manufacturer", [])),
            _matches_name(observed.get("name_zh"), name_zh, aliases.get("name_zh", [])),
        )
        if not checks[0]:
            continue
        evidence = [field for field, matched in zip(PRIORITIES, checks) if matched]
        if all(checks):
            full.append(dict(status="matched", drug_id=drug_id, source_id=source_id,
                             license_number=license_no, name_zh=name_zh, name_en=name_en,
                             matched_fields=evidence))
        else:
            partial.append((len(evidence), drug_id))
    if len(full) == 1:
        return full[0]
    if full:
        return {"status": "ambiguous", "candidate_ids": sorted(row["drug_id"] for row in full)}
    partial.sort(key=lambda row: (-row[0], row[1]))
    return {"status": "not_found", "candidate_ids": [drug_id for _, drug_id in partial]}
