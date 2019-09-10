class LineBuffer:
    def __init__(self):
        self.lines = []
        self.chars = ''
        self.annotations = []

    def has_line(self):
        return bool(self.lines)

    def push(self):
        self.lines.append((self.annotations, self.chars))
        self.chars = ''
        self.annotations = []

    def pop(self):
        if not self.lines:
            return ([], None)
        annotations, line = self.lines.pop(0)
        return annotations, line

    def append(self, text):
        while text:
            nl = text.find('\n')
            if nl == -1:
                self.chars += text
                text = ''
            else:
                line, text = text[:nl + 1], text[nl + 1:]
                self.chars += line
                self.push()

    def annotate(self, annotation):
        self.annotations.append(annotation)

        # We use annotations primarily to support telnet IAC DO TM.
        # Hypothetically this could come after any character, so we
        # annotate the line containing that character so that the caller
        # knows where it came up. In practice, though, this comes right
        # after a telnet IAC IP, which causes a .clear(). So, as a special
        # case, if our current line is empty and get an annotation, push
        # that annotation without any line so that the caller can get it as
        # quickly as possible.
        if not self.chars:
            self.push()

    def clear(self):
        self.lines = []
        self.chars = ''
