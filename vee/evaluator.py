from tokenizer import TokenType
from parser import Node, NodeType


class Evaluator:
    def __init__(self):
        self.env = {
            'true': True,
            'false': False,
        }
        self.frames = []
        self.funcs = {}

    def evaluate(self, ast):
        node_type = ast.type
        token = ast.token
        children = ast.children
        match node_type:
            case NodeType.VALUE:
                if token.type == TokenType.NUM:
                    if '.' in token.value:
                        return float(token.value)
                    else:
                        return int(token.value)
                return token.value
            case NodeType.IDENT:
                # TODO loop up in stack
                if self.frames and token.value in self.frames[-1]:
                    return self.frames[-1][token.value]
                return self.env[token.value]
            case NodeType.FUNC_DEF:
                self.funcs[children[0].token.value] = ast
            case NodeType.RETURN:
                result = self.evaluate(children[0])
                self.frames.pop()
                return ('RETURN_SIG', result)
            case NodeType.OPERATOR:
                if token.value == '=':
                    left_id = children[0].token.value
                    self.env[left_id] = self.evaluate(children[1])
                else:
                    left_val = self.evaluate(children[0])
                    right_val = self.evaluate(children[1])
                    match token.value:
                        case '.':
                            if children[0].token.type==TokenType.NUM and children[1].token.type==TokenType.NUM:
                                return float(f'{left_val}.{right_val}')
                            if children[1].token.value == 'len':
                                return len(left_val)
                    match token.value:
                        case '+':
                            if children[0].token.type==TokenType.NUM and children[1].token.type==TokenType.NUM:
                                return float(left_val) + float(right_val)
                            return left_val + right_val
                            # TODO int + str
                        case '-':
                            return int(left_val) - int(right_val)
                        case '*':
                            return float(left_val) * float(right_val)
                        case '/.':
                            return float(left_val) / float(right_val)
                        case '/':
                            return left_val // right_val
                        case '<':
                            return float(left_val) < float(right_val)
                        case '<=':
                            return float(left_val) <= float(right_val)
                        case '>':
                            return float(left_val) > float(right_val)
                        case '>=':
                            return float(left_val) >= float(right_val)
                        case '==':
                            return left_val == right_val
                        case '..':
                            return range(int(left_val), int(right_val))
                        case '[':
                            return left_val[int(right_val)]
                        case ':':
                            return (left_val, right_val)
                        case '&&':
                            return left_val and right_val
                        case '||':
                            return left_val or right_val
                        case _:
                            raise SyntaxError(f'unhandled operator: {token}')
            case NodeType.EXPR_LIST:
                return [self.evaluate(expr) for expr in children]
            case NodeType.STMT_LIST:
                result = None
                for stmt in ast.children:
                    result = self.evaluate(stmt)
                    if type(result) == tuple and len(result) == 2 and result[0] == 'RETURN_SIG':
                        return result
                return result
            case NodeType.FUNC_CALL:
                params = []
                if children:
                    params = self.evaluate(children[0])
                if token.value == 'print':
                    print(*params)
                elif token.value == 'type':
                    return str(type(params[0]).__name__)
                else:
                    func = self.funcs[token.value]
                    frame = {}
                    for i, arg in enumerate(func.children[1].children):
                        frame[arg.token.value] = params[i]
                    self.frames.append(frame)
                    result = self.evaluate(func.children[2])
                    if type(result) == tuple and len(result) == 2 and result[0] == 'RETURN_SIG':
                        return result[1]
                    return result
            case NodeType.IF:
                condition_index = 0
                while condition_index < len(children) // 2:
                    cond = self.evaluate(children[condition_index * 2])
                    if cond:
                        return self.evaluate(children[condition_index * 2 + 1])
                    condition_index += 1
            case NodeType.FOR:
                var = children[0].children[0].token.value
                val_range = self.evaluate(children[0].children[1])
                body = children[1]
                this_frame = {}
                self.frames.append(this_frame)
                result = None
                for val in val_range:
                    this_frame[var] = val
                    result = self.evaluate(body)
                    if type(result) == tuple and len(result) == 2 and result[0] == 'RETURN_SIG':
                        break
                self.frames.pop()
                return result
        