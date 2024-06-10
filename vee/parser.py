from enum import Enum
from tokenizer import TokenType

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
                child.pretty_print(indent + f'{child_head}  ', i == len(self.children) - 1)

class NodeType(Enum):
    EXPR_LIST = 1
    STMT_LIST = 2
    OPERATOR = 3
    IDENTIFIER = 4
    VALUE = 5
    LIST = 6
    FUNC_CALL = 7
    FUNCTION = 10
    FOR = 11
    IF = 12
    TODO = 999

KEY_WORDS = [
    'class',
    'func',
    'for',
    'if',
    'else'
]

PRECEDENCE = {
    '=': 0,
    '==': 1,
    '!=': 1,
    '>': 1,
    '<': 1,
    '+': 2,
    '-': 2,
    '*': 3,
    '/': 3,
    '.': 99,
}

LEFT_ASSOCIATIVE = {'+', '-', '*', '/'}

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def consume(self, type=None, value=None):
        token = self.tokens[self.pos]
        if type and token.type != type:
            raise SyntaxError(f'Unexpected token: {token}, expected {type}')
        if value and token.value != value:
            raise SyntaxError(f'Unexpected token: {token}, expected {value}')
        self.pos += 1
        return token

    def peek(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        else:
            raise SyntaxError()

    def parse_expression(self, min_precedence=0):
        token = self.peek()
        if not token:
            return None
    
        if token.type == TokenType.SYM and token.value in ('{', '}', ']'):
            return None
        
        while token.type == TokenType.NEL:
            self.consume()
            return self.parse_expression()

        node = self.parse_factor()
        while True:
            token = self.peek()
            if (token.type == TokenType.NEL or
                    (token.type == TokenType.SYM and
                    token.value in ('{', '}', ']'))
            ):
                # newline is the end of expression
                break
            if token is None or token.value not in PRECEDENCE:
                break

            precedence = PRECEDENCE[token.value]
            if precedence < min_precedence:
                break

            self.consume()
            left = node
            right = self.parse_expression(precedence + 1 if token.value in LEFT_ASSOCIATIVE else precedence)
            node = Node(NodeType.OPERATOR, token)
            node.children.append(left)
            node.children.append(right)

        # if node:
        #     node.pretty_print(indent='', is_last=True)
        return node

    def parse_expression_list(self):
        # TODO: support both () and []
        token = self.consume(type=TokenType.SYM, value='(')
        node = Node(NodeType.EXPR_LIST, token)
        while self.peek().value != ')':
            arg = self.parse_expression()
            node.children.append(arg)
            if self.peek().value == ',':
                self.consume()
        self.consume(type=TokenType.SYM, value=')')
        return node

    def parse_factor(self):
        token = self.peek()
        node = None
        if token.value == '[':
            # list literal
            self.consume(value='[')
            node = Node(NodeType.LIST, token)
            if self.peek().value != ']':
                node.children.append(self.parse_expression())
            while self.peek().value != ']':
                self.consume(value=',')
                node.children.append(self.parse_expression())
            self.consume(value=']')
        else:
            node = self.parse_atom()
        return node

    def parse_atom(self):
        token = self.consume()
        if token.type == TokenType.IDN:
            node = Node(NodeType.IDENTIFIER, token)
            # Lookahead to check if it's a function call
            if self.pos < len(self.tokens) and self.peek().value == '(':
                args = self.parse_expression_list()
                node = Node(NodeType.FUNC_CALL, token)
                node.children.append(args)
            return node
        elif token.type in (TokenType.STR, TokenType.NUM) :
            return Node(NodeType.VALUE, token)
        elif token.value == '(':
            node = self.parse_expression()
            self.consume(value=')')  # consume ')'
            return node
        raise SyntaxError(f'Unexpected token: {token}')


    def parse_stmt(self):
        token = self.peek()
        stmt_type = token.value
        match stmt_type:
            case 'if':
                node =  Node(NodeType.IF, token)
                self.consume()
                node.children.append(self.parse_expression())
                self.consume(value='{')
                true_clause = self.parse_stmt_list()
                self.consume(value='}')
                node.children.append(true_clause)
                # TODO optional else
                return node
            case 'func':
                node =  Node(NodeType.FUNCTION, token)
                # TODO
                while self.peek().value != '}':
                    self.consume()
                self.consume(value='}')
                return node
            case 'for':
                node =  Node(NodeType.FOR, token)
                while self.peek().value != '}':
                    self.consume()
                self.consume(value='}')
                return node
            case _:
                return Node(NodeType.TODO, token)

    def parse_stmt_list(self):
        root = Node(NodeType.STMT_LIST, None)
        ast = root
        while self.pos < len(self.tokens):
            if self.peek().type == TokenType.KEY:
                ast.children.append(self.parse_stmt())
            elif self.peek().type == TokenType.NEL:
                self.consume()
                continue
            elif self.peek().type == TokenType.EOF:
                break
            else:
                node = self.parse_expression()
                if node:
                    ast.children.append(node)
                else:
                    break
        return root

    def parse(self):
        return self.parse_stmt_list()
