class LineBuffer:
    def __init__(self):
        self.lines = []
        self.chars = ''

    def has_line(self):
        return bool(self.lines)

    def pop(self):
        if not self.lines:
            return None

        line = self.lines[0]
        self.lines = self.lines[1:]
        return line

    def append(self, text):
        while text:
            nl = text.find('\n')
            if nl == -1:
                self.chars += text
                text = ''
            else:
                line, text = text[:nl + 1], text[nl + 1:]
                self.chars += line
                self.lines.append(self.chars)
                self.chars = ''
