"""Request-local answer-key selection; never caches images across requests."""
import json


def parts_signature(answer_key):
    """Match effective process_sheet limits, including an unrestricted section."""
    try:
        data = json.loads(answer_key) if answer_key else {}
    except (ValueError, TypeError):
        return (None, None, None)
    parts = data.get('parts') if isinstance(data, dict) else None
    if not isinstance(parts, (list, tuple)):
        return (None, None, None)
    return tuple(parts[i] if i < len(parts) else None for i in range(3))


class LiveAnswerKeySelection:
    """Choose before scoring/rendering; different read limits retain old rerun.

    Construct per request, using already teacher-scoped variants. The engine
    calls resolve exactly once after recognition, without mutating its reading.
    """
    def __init__(self, first_key, variants, parse_key, strict=False, choose_early=True):
        self.first_key = first_key
        self.used_key = first_key
        self.variants = tuple((str(code), key) for code, key in variants)
        self.parse_key = parse_key
        self.strict = strict
        self.choose_early = choose_early

    def validate(self, detected_code):
        code = str(detected_code or '')
        if not code or not code.isascii() or not code.isdigit():
            raise ValueError('Mã đề chưa đọc rõ hoặc tô nhiều ô. Vui lòng quét lại.')
        if not any(code == registered for registered, _ in self.variants):
            raise ValueError(f'Mã đề {code} chưa được khai báo trong đề thi này. Không chấm bài.')

    def resolve(self, detected_code):
        if self.strict:
            self.validate(detected_code)
        key = next((key for code, key in self.variants
                    if code == str(detected_code)), self.first_key)
        if not self.choose_early or parts_signature(key) != parts_signature(self.first_key):
            key = self.first_key
        parsed = self.parse_key(key)
        self.used_key = key
        return parsed
