from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Independent ASCII cell recognition using a separately captured native reference sheet.

No expected command text is used to choose a glyph. Unknown or ambiguous shapes
remain unverified. References use the same capture configuration and font.
"""

ASCII = ''.join(chr(i) for i in range(33, 127))
REFERENCE_GLYPHS = ASCII + '·•›‹└✔✓√'  # UI punctuation plus nearby confusable shapes.
STYLES = ('0', '1', '3', '1;3', '4', '1;4', '3;4', '1;3;4')


def reference_sheet(alphabet=REFERENCE_GLYPHS):
    payload = ''; labels = []
    for style in STYLES:
        for start in range(0, len(alphabet), 40):
            chars = alphabet[start:start+40]
            row = len(labels)
            labels.append([{'row': row, 'column': col*2, 'text': char} for col, char in enumerate(chars)])
            payload += '\x1b[0m\x1b['+style+'m'+' '.join(chars)+'\x1b[0m\n'
    return payload, [cell for row in labels for cell in row]


def crop_cell(image, geometry, row, column):
    x = round(geometry['x'] + column*geometry['cell_width'])
    end = round(geometry['x'] + (column+1)*geometry['cell_width'])
    y = geometry['y'] + (row+2)*geometry['cell_height']
    if x < 0 or y < 0 or end > image.width or y+geometry['cell_height'] > image.height:
        raise ValueError('Glyph cell clipped')
    return image.crop((x, y, end, y+geometry['cell_height']))


def mask(cell):
    # Normalize ink coverage instead of matching palette colors. The independent
    # pixel/contrast gate must still pass; normalization cannot rescue faint text.
    gray = cell.convert('L')
    values = list(gray.get_flattened_data())
    dark, light = min(values), max(values)
    if light-dark < 20:
        return frozenset()
    threshold = (dark+light)/2
    return frozenset(i for i,v in enumerate(values) if v < threshold)


def distance(a, b):
    if not a or not b:
        return 0.0 if a == b else 1.0
    return len(a ^ b)/(len(a)+len(b))


def classify(ink, templates, maximum=.08, margin=.04):
    if not ink:
        return ' ', 0.0
    # Compete against the entire alphabet, across all styles, before comparing
    # with expected text. Never limit alternatives to the expected character.
    scores = sorted((min(distance(ink, sample) for sample in samples), char)
                    for char, samples in templates.items())
    best, char = scores[0]
    if best > maximum or (len(scores)>1 and scores[1][0]-best < margin):
        return None, best
    return char, best


def templates_from_capture(image, geometry):
    labels = geometry.get('reference_labels', reference_sheet()[1])
    templates = {}
    for cell in labels:
        ink = mask(crop_cell(image, geometry, cell['row'], cell['column']))
        if not ink:
            raise ValueError('Reference glyph missing: '+repr(cell['text']))
        templates.setdefault(cell['text'], []).append(ink)
    return templates


def recognize_rows(image, geometry, rows, templates, columns=120):
    recognized = {}; unknown = []; cache = {}
    for row in rows:
        chars = []
        for column in range(columns):
            ink = mask(crop_cell(image, geometry, row, column))
            if ink not in cache:
                cache[ink] = classify(ink, templates)
            char, score = cache[ink]
            chars.append(char if char is not None else '\ufffd')
            if char is None:
                unknown.append({'row': row, 'column': column, 'distance': round(score, 4)})
        recognized[row] = ''.join(chars)
    return recognized, unknown


def recover_content(content, image, geometry, reference_image, reference_geometry):
    if (geometry['cell_width'], geometry['cell_height']) != (reference_geometry['cell_width'], reference_geometry['cell_height']):
        raise ValueError('Reference glyph geometry differs from command frame')
    templates = templates_from_capture(reference_image, reference_geometry)
    # A row must match in full, including any unexpected suffix, to be recovered.
    recognized, unknown = recognize_rows(image, geometry,
                                         [r['row'] for r in content['mismatches']], templates)
    remaining = []; recovered = []
    for mismatch in content['mismatches']:
        row = mismatch['row']; observed = recognized[row]
        evidence = dict(mismatch, glyph_observed=observed.rstrip())
        if ''.join(observed.split()) == ''.join(mismatch['expected'].split()):
            recovered.append(evidence)
        else:
            remaining.append(evidence)
    return dict(content, status='unverified' if remaining else 'pass', mismatches=remaining,
                glyph_recovered=recovered, glyph_unknown=unknown,
                glyph_scope='Independent native ASCII reference, all glyphs/styles compete; full 120-column rows. Shape threshold .08; ambiguity margin .04; no punctuation substitutions.')
