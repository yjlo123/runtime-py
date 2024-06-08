from enum import Enum
from tokenizer import TokenType

class Node:
    def __init__(self, type, token):
        self.type = type
        self.token = token
        self.children = []

    def __repr__(self):
        return f'[{self.type.name}]{self.token}-{[c for c in self.children]}'

class NodeType(Enum):
    ROOT = 1
    OPERATOR = 2
    IDENTIFIER = 3
    VALUE = 4
    LIST = 5
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

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def consume(self, type=None, value=None):
        token = self.tokens[self.pos]
        if type and token.type != type:
            raise SyntaxError(f'Unexpected token: {token}')
        if value and token.value != value:
            raise SyntaxError(f'Unexpected token: {token}')
        self.pos += 1
        return token

    def peek(self):
        return self.tokens[self.pos]

    def parse_expression(self):
        if self.peek().type == TokenType.EOF:
            return None
        while self.peek().type == TokenType.NEL:
            self.consume()
            return self.parse_expression()
        return self.parse_term()

    def parse_term(self):
        node = self.parse_factor()
        while self.pos < len(self.tokens) and self.peek().value in ('='):
            token = self.consume()
            left = node
            node = Node(NodeType.OPERATOR, token)
            node.children.append(left)
            node.children.append(self.parse_factor())
        return node

    def parse_factor(self):
        token = self.peek()
        node = None
        if token.value == '[':
            # list literal
            self.consume(value='[')
            node = Node(NodeType.LIST, token)
            if self.peek().value != ']':
                node.children.append(self.parse_term())
            while self.peek().value != ']':
                self.consume(value=',')
                node.children.append(self.parse_term())
            self.consume(value=']')
        else:
            node = self.parse_atom()
            # while self.pos < len(self.tokens) and token.value in ('*'):
            #     token = self.consume()
            #     node = (token, node, self.parse_atom())
        return node

    def parse_atom(self):
        token = self.consume()
        if token.type == TokenType.IDN:
            return Node(NodeType.IDENTIFIER, token)
        elif token.type in (TokenType.STR, TokenType.NUM) :
            return Node(NodeType.VALUE, token)
        elif token.value == '(':
            node = self.parse_expression()
            self.consume(value=')')  # consume ')'
            return node
        raise SyntaxError(f'Unexpected token: {token}')


    def parse_statement(self):
        token = self.peek()
        stmt_type = token.value
        match stmt_type:
            case 'if':
                node =  Node(NodeType.IF, token)
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
                return node
            case _:
                return Node(NodeType.TODO, token)

    def parse(self):
        root = Node(NodeType.ROOT, None)
        ast = root
        while self.pos < len(self.tokens):
            if self.peek().type == TokenType.KEY:
                ast.children.append(self.parse_statement())
            elif self.peek().type == TokenType.NEL:
                self.consume()
                continue
            elif self.peek().type == TokenType.EOF:
                break
            else:
                node = self.parse_expression()
                if node:
                    ast.children.append(node)
        return root
