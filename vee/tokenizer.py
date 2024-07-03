from enum import Enum

class TokenType(Enum):
    KEY = 1    # keyword
    IDN = 2    # identifier
    NUM = 3    # number
    STR = 4    # string
    NEL = 5    # newline
    SYM = 6    # symbol
    EOF = 99   # end of file
    NON = 100  # none

class Token:
    def __init__(self, value, type, line, column):
        self.value = value
        self.type = type
        self.line = line
        self.column = column

    def __str__(self):
        return f'{self.value} ({self.type.name})[{self.line}:{self.column}]'

KEY_WORDS = [
    'class', 'func', 'for', 'while', 'if', 'return'
]

MULTI_CHAR_OPERATORS = {
    '=': {'==', '=>'},
    '>': {'>='},
    '<': {'<='},
    '!': {'!='},
    '+': {'+=', '++'},
    '-': {'-=', '--'},
    '*': {'*=', '**'},
    '/': {'/=', '/.', '/.='},
    '%': {'%='},
    '&': {'&&'},
    '|': {'||'},
    '.': {'..'},
}

class Tokenizer:
    def __init__(self):
        self.tokens = []
        self.line = 1
        self.column = 1
        self.current = ''

    def add_current_token(self):
        if self.current:
            type = TokenType.NON
            if self.current.isdigit():
                type = TokenType.NUM
            elif self.current in KEY_WORDS:
                type = TokenType.KEY
            else:
                type = TokenType.IDN
            self.tokens.append(Token(self.current, type, self.line, self.column))
            self.column += len(self.current)
            self.current = ''

    def add_token(self, value, type):
        self.tokens.append(Token(value, type, self.line, self.column))
        self.column += len(value or '')

    def tokenize(self, src):
        quote = None
        comment = None
        operator = None
        for c in src:
            if quote is not None:
                if c != quote:
                    self.current += c
                else:
                    self.add_token(self.current, TokenType.STR)
                    self.column += 2  # for left and right quote
                    self.current = ''
                    quote = None
                continue

            if comment is not None:
                if c == '\n':
                    self.line += 1
                if comment == '\n':
                    if c == '\n':
                        comment = None
                    continue
                elif comment == '*':
                    if c == '*':
                        comment = '**'
                    continue
                elif comment == '**':
                    if c == '/':
                        comment = None
                    else:
                        comment = '*'
                    continue
                else:
                    # comment is ?
                    if c == '/':
                        # single-line comment
                        comment = '\n'
                        continue
                    elif c == '*':
                        # multi-line comment
                        comment = '*'
                        continue
                    else:
                        # not comment
                        self.current = '/'
                        if '/' in MULTI_CHAR_OPERATORS:
                            operator = 1
                        comment = None
            elif c == '/':
                # new comment
                comment = '?'
                continue

            if operator is not None:
                if (not (c.isalpha() or c.isdigit())
                    and self.current + c in MULTI_CHAR_OPERATORS[self.current[0]]):
                    self.current += c
                    operator += 1
                    continue
                self.add_token(self.current, TokenType.SYM)
                self.current = ''
                operator = None
                    
            if c in [' ', '\t', '\n', '\r']:
                self.add_current_token()
                self.column += 1
                if c == '\n':
                    self.add_token('(<-|)', TokenType.NEL)
                    self.line += 1
                    self.column = 1
            elif c in ['\'', '"', '`']:
                quote = c
                assert(self.current == '')
            elif not (c.isalpha() or c.isdigit() or c == '_'):
                self.add_current_token()
                if c in MULTI_CHAR_OPERATORS:
                    operator = 1
                    self.current = c
                else:
                    self.add_token(c, TokenType.SYM)
            else:
                self.current += c

        self.add_current_token()
        self.add_token(None, TokenType.EOF)
        return self.tokens

def print_tokens(tokens):
    for t in tokens:
        print(f'{t.line:3}:{t.column:2} {t.type.name} {t.value}')
