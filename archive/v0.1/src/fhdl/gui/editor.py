from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import QRegularExpression, Qt
import re

class FHDLSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        # 키워드 포맷 (node, pipe, valve 등)
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569cd6"))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = ["node", "pipe", "valve", "Material", "Preset", "PumpCurve", 
                    "System_Setup", "Component_Library", "Topology", "Sequence"]
        for word in keywords:
            pattern = QRegularExpression(f"\\b{word}\\b", QRegularExpression.CaseInsensitiveOption)
            self.highlighting_rules.append((pattern, keyword_format))

        # 데이터 타입/상태 포맷 (TANK, PUMP, JUNCTION 등)
        type_format = QTextCharFormat()
        type_format.setForeground(QColor("#4ec9b0"))
        types = ["TANK", "PUMP", "JUNCTION", "TERMINAL", "CHECK", "OPEN", "CLOSED"]
        for t in types:
            pattern = QRegularExpression(f"\\b{t}\\b")
            self.highlighting_rules.append((pattern, type_format))

        # 숫자 포맷
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8"))
        self.highlighting_rules.append((QRegularExpression("\\b[\\d.]+\\b"), number_format))

        # 주석 포맷
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        self.highlighting_rules.append((QRegularExpression("//.*"), comment_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            expression = QRegularExpression(pattern)
            it = expression.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)

class FHDLLinter:
    """텍스트 기반 실시간 오타 및 구조 검증기"""
    @staticmethod
    def validate(text: str) -> list:
        errors = []
        lines = text.split('\n')
        
        # 1. 중괄호 쌍 검사
        open_braces = text.count('{')
        close_braces = text.count('}')
        if open_braces != close_braces:
            errors.append(f"Structure Error: Mismatched braces ({{: {open_braces}, }}: {close_braces})")

        # 2. 알려진 키워드 오타 검사 (간이 로직)
        known_keywords = ["node", "pipe", "valve", "material", "preset", "pumpcurve", 
                          "system_setup", "component_library", "topology", "sequence"]
        
        # 블록 시작 단어만 추출하여 검사
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith("//"): continue
            
            # 단어만 추출 (괄호나 숫자 제외)
            first_word = re.match(r'^(\w+)', line)
            if first_word:
                word = first_word.group(1).lower()
                # 키워드 후보군에 없는데 일반적인 단어 형태인 경우 오타로 의심
                if word not in known_keywords and not re.match(r'^(n|p|v)\d+', word):
                    # 블록 내부의 설정값(Temp 등)은 제외하는 등 정교화 필요
                    pass 

        return errors
