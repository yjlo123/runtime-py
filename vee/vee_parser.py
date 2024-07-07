from enum import Enum
from tokenizer import Token, TokenType


class Node:
    def __init__(self, type, token):
        self.type = type
        self.token = token
        self.children = []

    def __repr__(self):
        return f'[{self.type.name}]{self.token}-{[c for c in self.children]}'

    def pretty_print(self, indent='  ', is_last=False):
        head = '└' if is_last else '├'
        print(f'{indent}{head}({self.type.name}) {self.token or ""}')
        child_head = ' ' if is_last else '│'
        if len(self.children) > 0:
            for i, child in enumerate(self.children):
                child.pretty_print(
                    indent + f'{child_head}  ', i == len(self.children) - 1)


class NodeType(Enum):
    IMPORT = 0
    EXPR_LIST = 1
    STMT_LIST = 2
    OPERATOR = 3
    IDENT = 4
    VALUE = 5
    ARG = 6
    FUNC_CALL = 7
    FUNC_DEF = 8
    ARG_LIST = 9
    FOR = 11
    WHILE = 12
    IF = 13
    ELSE = 14
    RETURN = 15
    CLASS = 16


PRECEDENCE = {
    '=': 0,
    '+=': 0,
    '-=': 0,
    '*=': 0,
    '/=': 0,
    '/.=': 0,
    '%=': 0,

    '=>': 1,

    '&&': 2,
    '||': 2,

    ':': 3,

    '..': 4,
    '==': 4,
    '!=': 4,
    '>': 4,
    '>=': 4,
    '<': 4,
    '<=': 4,

    '+': 5,
    '-': 5,

    '*': 6,
    '/': 6,
    '/.': 6,
    '%': 6,

    '++': 10,
    '--': 10,
    '**': 10,
    '.': 99,
}

LEFT_ASSOCIATIVE = {'+', '-', '*', '/', '&&', '||', '.'}

LIST_PAIR = {
    '(': ')',
    '[': ']',
    '{': '}',
}


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def consume(self, type=None, value=None):
        token = self.tokens[self.pos]
        if type and token.type != type:
            raise SyntaxError(
                f'Unexpected token: {token}, expected type: {type}')
        if value and token.value != value:
            raise SyntaxError(
                f'Unexpected token: {token}, expected value: {value}')
        self.pos += 1
        return token

    def peek(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        else:
            raise SyntaxError()

    def peek_check(self, value, type=None):
        if self.pos >= len(self.tokens):
            return False
        if type and self.peek().type != type:
            return False
        return self.peek().value == value

    def peek_check_over_paren(self, value, type=None, open_paren='('):
        close_paren = LIST_PAIR[open_paren]
        count = 1
        ptr = self.pos + 1
        while ptr < len(self.tokens) and count > 0:
            if self.tokens[ptr].value == open_paren:
                count += 1
            elif self.tokens[ptr].value == close_paren:
                count -= 1
            ptr += 1
        if ptr >= len(self.tokens):
            return False
        return self.tokens[ptr].value == value

    def parse_expression(self, min_precedence=0):
        token = self.peek()

        # check if it's nothing to parse as expression next
        if token.type == TokenType.SYM and token.value in ('}', ']', ')'):
            # '{' is a valid starting expression symbol
            return None

        while token.type == TokenType.NEL:
            self.consume()
            return self.parse_expression()

        node = self.parse_atom()
        while True:
            token = self.peek()
            if (token.type == TokenType.NEL or
                (token.type == TokenType.SYM and
                    token.value in ('{', '}', ']'))):
                # newline is the end of expression
                # incoming non-operator symbols -> end of expression
                # '{' is not a valid operator here
                break
            if token is None or token.value not in PRECEDENCE:
                break

            precedence = PRECEDENCE[token.value]
            if precedence < min_precedence:
                break

            self.consume()
            left = node
            right = self.parse_expression(
                precedence + 1
                if token.value in LEFT_ASSOCIATIVE else
                precedence)
            node = Node(NodeType.OPERATOR, token)
            node.children.append(left)
            node.children.append(right)

        # if node:
        #     node.pretty_print(indent='', is_last=True)
        return node

    def parse_expression_list(self, left):
        right = LIST_PAIR[left]
        token = self.consume(type=TokenType.SYM, value=left)
        node = Node(NodeType.EXPR_LIST, token)
        while self.peek().value != right:
            arg = self.parse_expression()
            if arg is not None:
                node.children.append(arg)
            if self.peek().value == ',':
                self.consume()
        self.consume(type=TokenType.SYM, value=right)
        return node

    def parse_atom(self):
        token = self.peek()
        if token.value in LIST_PAIR and token.value != '(':
            return self.parse_expression_list(token.value)
        elif token.type == TokenType.SYM and token.value == '-':
            # unary operator
            token = self.consume()
            node = Node(NodeType.OPERATOR, token)
            node.children.append(self.parse_atom())
            return node
        elif token.type == TokenType.IDN:
            token = self.consume()
            node = Node(NodeType.IDENT, token)
            # Lookahead to check if it's a function call
            if self.peek_check('('):
                args = self.parse_expression_list('(')
                node = Node(NodeType.FUNC_CALL, token)
                node.children.append(args)
            # check if it's getting value by index/key
            else:
                while self.peek_check('['):
                    idn_node = node
                    left = self.consume(type=TokenType.SYM, value='[')
                    node = Node(NodeType.OPERATOR, left)
                    node.children.append(idn_node)
                    node.children.append(self.parse_expression())  # index
                    self.consume(type=TokenType.SYM, value=']')
            return node
        elif token.type in (TokenType.STR, TokenType.NUM):
            token = self.consume()
            return Node(NodeType.VALUE, token)
        elif token.value == '(':
            # lookahead to check if it's a lambda
            if self.peek_check_over_paren('=>'):
                node = self.parse_args()
            else:
                token = self.consume(value='(')
                node = self.parse_expression()
                self.consume(value=')')
            return node
        elif token.value == 'if':
            return self.parse_if(token)
        raise SyntaxError(f'Unexpected token: {token}')

    def parse_block(self):
        self.consume(value='{')
        block = self.parse_stmt_list()
        self.consume(value='}')
        return block
    
    def parse_args(self):
        token = self.consume(TokenType.SYM, '(')
        node = Node(NodeType.ARG_LIST, token)
        if not self.peek_check(')'):
            arg = self.consume(type=TokenType.IDN)
            node.children.append(Node(NodeType.IDENT, arg))
            while self.peek_check(','):
                self.consume(TokenType.SYM, ',')
                arg = self.consume(type=TokenType.IDN)
                node.children.append(Node(NodeType.IDENT, arg))
        self.consume(TokenType.SYM, ')')
        return node

    def parse_if(self, token):
        node = Node(NodeType.IF, token)
        self.consume(value='if')
        node.children.append(self.parse_expression())
        node.children.append(self.parse_block())
        while self.peek_check('else'):
            token_else = self.consume(value='else')
            if self.peek_check('if'):
                # case else if
                self.consume(value='if')
                node.children.append(self.parse_expression())
                node.children.append(self.parse_block())
            else:
                # case else: virtual token (always 'true' for the last else)
                node.children.append(Node(NodeType.VALUE, Token('true', TokenType.IDN, token_else.line, token_else.column)))
                node.children.append(self.parse_block())
        return node

    def parse_stmt(self):
        token = self.peek()
        stmt_type = token.value
        node = None
        match stmt_type:
            case 'import':
                node = Node(NodeType.IMPORT, token)
                self.consume(value=stmt_type)
                node.children.append(self.parse_expression())
            case 'func':
                node = Node(NodeType.FUNC_DEF, token)
                self.consume(value=stmt_type)
                node.children.append(
                    Node(NodeType.VALUE, self.consume())
                )  # func name
                node.children.append(self.parse_args())
                node.children.append(self.parse_block())
            case 'for' | 'while':
                node = Node(NodeType.FOR if stmt_type == 'for' else NodeType.WHILE, token)
                self.consume(value=stmt_type)
                node.children.append(self.parse_expression())
                if stmt_type == 'for':
                    self.consume(type=TokenType.KEY, value='in')
                    node.children.append(self.parse_expression())
                node.children.append(self.parse_block())
            case 'return':
                node = Node(NodeType.RETURN, token)
                self.consume(value=stmt_type)
                node.children.append(self.parse_expression())
            case 'class':
                node = Node(NodeType.CLASS, token)
                self.consume(value=stmt_type)
                node.children.append(
                    Node(NodeType.VALUE, self.consume())
                )  # class name
                node.children.append(self.parse_block())
            case _:
                raise SyntaxError(f'Unhandled keyword for statement: {token}')
        return node

    def parse_stmt_list(self):
        ast = Node(NodeType.STMT_LIST, None)
        while self.pos < len(self.tokens):
            if self.peek().type == TokenType.KEY and self.peek().value != 'if':
                # statement
                ast.children.append(self.parse_stmt())
            elif self.peek().type == TokenType.NEL:
                # newline
                self.consume()
                continue
            elif self.peek().type == TokenType.EOF:
                # EOF
                break
            else:
                # expression
                node = self.parse_expression()
                if node:
                    ast.children.append(node)
                else:
                    # end of statement list
                    break
        return ast

    def parse(self):
        return self.parse_stmt_list()
