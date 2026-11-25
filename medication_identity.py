"""Conservative drug identity matching using existing names/ingredient/license fields.

No database writes, learned aliases, or model-invented spelling corrections.
"""
import re
import unicodedata
from decimal import Decimal

MISSING = {'', '未標示', '看不清楚', '無法確認', '未提供'}
LABELS = {
    '商品名': 'trade_name', '商品名稱': 'trade_name', '中文名': 'name_zh',
    '中文名稱': 'name_zh', '學名': 'ingredient', '成分': 'ingredient',
    '含量': 'strength', '包裝量': 'package_size', '劑型': 'dosage_form', '廠牌': 'manufacturer',
    '製造廠': 'manufacturer', '許可證字號': 'license_number',
}
STRENGTH_RE = re.compile(
    r'(?<![\d.])(\d+(?:\.\d+)?)\s*(mcg|μg|ug|mg|g|微克|毫克|公克|%)'
    r'(?![a-z])(?:\s*/\s*(\d+(?:\.\d+)?)?\s*(ml|毫升|l|公升)(?![a-z]))?', re.I)


def clean(value):
    return unicodedata.normalize('NFKC', str(value or '')).strip().casefold()


def present(value):
    return str(value or '').strip() not in MISSING


def extract_identity(name_block):
    """Parse new labeled OCR output; keep legacy combined names readable."""
    result = {'raw_name': name_block.strip()}
    conflicts = []
    for line in name_block.splitlines():
        match = re.match(r'^\s*[・•*\-]?\s*([^：:]+)[：:]\s*(.*)$', line)
        if not match:
            continue
        key = LABELS.get(match.group(1).strip())
        value = match.group(2).strip()
        if key and present(value):
            if key in result and result[key] != value:
                conflicts.append(key)
            result[key] = value
    if conflicts:
        result['conflicting_fields'] = conflicts
    if len(result) == 1:
        # Some OCR responses join brand, generic and Chinese product name with 、.
        parts = [part.strip() for part in name_block.split('、')]
        if (len(parts) == 3 and all(parts)
                and re.search(r'[A-Za-z]', parts[0])
                and re.fullmatch(r'[A-Za-z][A-Za-z0-9 ().,+/-]*', parts[1])
                and re.search(r'[\u3400-\u9fff]', parts[2])):
            result.update(trade_name=parts[0], ingredient=parts[1], name_zh=parts[2])
            return result
        # Old output often joins brand and generic with a semicolon.
        parts = re.split(r'[;；\n]', name_block, maxsplit=1)
        result['trade_name'] = parts[0].strip()
        if len(parts) == 2 and present(parts[1]):
            result['ingredient'] = parts[1].strip()
    return result


def strengths(text):
    """Normalize mass units while preserving concentration denominators."""
    found = set()
    for match in STRENGTH_RE.finditer(clean(text)):
        number, unit, denominator, volume = match.groups()
        amount = Decimal(number)
        if unit in ('g', '公克'):
            amount *= 1000
        elif unit in ('mcg', 'μg', 'ug', '微克'):
            amount /= 1000
        if volume:
            divisor = Decimal(denominator or '1')
            if volume in ('l', '公升'):
                divisor *= 1000
            if divisor == 0:
                found.add(('invalid', 'invalid'))
                continue
            amount /= divisor
        dimension = 'percent' if unit == '%' else 'mg/ml' if volume else 'mg'
        found.add((format(amount.normalize(), 'f'), dimension))
    return found


def dosage_form(text):
    text = clean(text)
    releases = set()
    for name, pattern in (
        ('extended', r'緩釋|持續性|長效|\b(?:sr|xr|er|cr|mr)\b|extended[ -]release|sustained[ -]release'),
        ('enteric', r'腸溶|腸衣|\be\.?\s*c\.?\b|enteric'),
    ):
        if re.search(pattern, text):
            releases.add(name)
    forms = set()
    for name, pattern in (
        ('film_tablet', r'膜衣錠|\bf\.?\s*c\.?\b|film[ -]coated'),
        ('sugar_tablet', r'糖衣錠|\bs\.?\s*c\.?\b|sugar[ -]coated'),
        ('capsule', r'膠囊|\bcaps?(?:ules?)?\b'),
        ('tablet', r'錠|\btabs?(?:lets?)?\b'),
        ('injection', r'注射|\binj(?:ection)?\b'),
        ('liquid', r'口服液|糖漿|\bsyrup\b|\bsolution\b'),
        ('cream', r'乳膏|\bcream\b'),
        ('ointment', r'軟膏|\bointment\b'),
    ):
        if re.search(pattern, text):
            forms.add(name)
    if 'film_tablet' in forms or 'sugar_tablet' in forms:
        forms.discard('tablet')
    return forms, releases


def product_name(text):
    """Separate brand identity from generic annotations, manufacturer and form."""
    text = clean(text)
    text = re.sub(r'「[^」]+」|『[^』]+』|"[^"]+"', ' ', text)
    text = re.sub(r'\([^)]*\)', ' ', text)
    text = STRENGTH_RE.sub(' ', text)
    text = re.sub(r'\b(?:film[ -]coated|sugar[ -]coated|tablets?|tabs?|capsules?|caps?|standard)\b', ' ', text)
    text = re.sub(r'\b[fse]\.?\s*c\.?\b', ' ', text)
    text = re.sub(r'膜衣錠|糖衣錠|腸溶錠|緩釋錠|膠囊|錠劑|錠|片', ' ', text)
    return re.sub(r'[^a-z0-9\u3400-\u9fff]+', '', text)


def license_key(text):
    return re.sub(r'\s+', '', clean(text))


def _ingredient_tokens(text):
    text = STRENGTH_RE.sub(' ', clean(text))
    ignored = {'each', 'contains', 'contain', 'tablet', 'tablets', 'capsule',
               'capsules', 'per', 'equivalent', 'to', 'as', 'and', 'of', 'in'}
    return {token for token in re.findall(r'[a-z][a-z0-9-]*', text) if token not in ignored}


def match_candidate(observed, candidate):
    """Return evidence only when supplied identity fields do not conflict."""
    if observed.get('conflicting_fields'):
        return None
    trade = observed.get('trade_name', '')
    chinese = observed.get('name_zh', '')
    raw = observed.get('raw_name', '')
    names = ' '.join(str(candidate.get(k) or '') for k in ('name_en', 'name_zh'))
    observed_names = ' '.join(filter(None, (trade, chinese, observed.get('strength'), observed.get('dosage_form'))))
    expected_strength = strengths(names)
    if not expected_strength:
        expected_strength = strengths(candidate.get('ingredient', ''))
    actual_strength = strengths(observed_names + ' ' + observed.get('ingredient', ''))
    # Multiple unequal component strengths need a component-to-strength mapping;
    # do not collapse a combination product into a single dose set.
    if len(actual_strength) > 1 or len(expected_strength) > 1:
        return None
    if actual_strength and expected_strength and actual_strength != expected_strength:
        return None
    actual_forms, actual_release = dosage_form(observed_names)
    expected_forms, expected_release = dosage_form(names)
    # Do not equate SR/ER/enteric formulations with ordinary products.
    if actual_release != expected_release and (actual_release or expected_release):
        return None
    if len(actual_forms) > 1 or len(expected_forms) > 1:
        return None
    if actual_forms and expected_forms and actual_forms != expected_forms:
        # A plain "Tab" may omit a coating; it must not mean a different base form.
        tablets = {'tablet', 'film_tablet', 'sugar_tablet'}
        if not (actual_forms == {'tablet'} and expected_forms <= tablets):
            return None
    observed_ingredient = observed.get('ingredient', '')
    actual_ingredients = _ingredient_tokens(observed_ingredient)
    expected_ingredients = _ingredient_tokens(candidate.get('ingredient', ''))
    if actual_ingredients and expected_ingredients and actual_ingredients != expected_ingredients:
        return None
    if present(observed_ingredient) and not actual_ingredients:
        compact = re.sub(r'\W', '', clean(observed_ingredient))
        if compact and compact not in re.sub(r'\W', '', clean(candidate.get('ingredient'))):
            return None
    manufacturer = clean(observed.get('manufacturer'))
    makers = re.findall(r'[「『"]([^」』"]+)[」』"]', candidate.get('name_zh') or '')
    if manufacturer and makers and manufacturer not in {clean(m) for m in makers}:
        return None
    actual_license = license_key(observed.get('license_number'))
    expected_license = license_key(candidate.get('license_number'))
    if actual_license and actual_license != expected_license:
        return None
    matched = []
    for key, value, expected in (
        ('trade_name', trade, candidate.get('name_en')),
        ('name_zh', chinese, candidate.get('name_zh')),
    ):
        if not present(value) or not expected:
            continue
        left, right = product_name(value), product_name(expected)
        if not left or not right or left != right:
            return None
        matched.append(key)
    if not matched and not trade and not chinese and raw:
        return None
    corroboration = []
    if actual_strength and expected_strength:
        corroboration.append('strength')
    if actual_ingredients and expected_ingredients:
        corroboration.append('ingredient')
    if manufacturer and makers:
        corroboration.append('manufacturer')
    if actual_forms and expected_forms:
        corroboration.append('dosage_form')
    if actual_license and expected_license:
        return ['license_number', *matched, *corroboration]
    # A generic ingredient alone is never a product identity.
    if not matched or not corroboration:
        return None
    return matched + corroboration


def resolve_medication(observed, candidates):
    matches = []
    for candidate in candidates:
        evidence = match_candidate(observed, candidate)
        if evidence:
            matches.append((candidate, evidence))
    ids = {candidate['drug_id'] for candidate, _ in matches}
    if len(ids) != 1:
        return {'status': 'ambiguous' if len(ids) > 1 else 'not_found',
                'candidate_ids': sorted(ids)}
    candidate, evidence = matches[0]
    return {'status': 'matched', 'drug_id': candidate['drug_id'],
            'source_id': candidate.get('source_id'), 'matched_fields': evidence,
            'license_number': candidate.get('license_number'),
            'name_zh': candidate.get('name_zh'), 'name_en': candidate.get('name_en')}

