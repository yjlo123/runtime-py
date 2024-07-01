from tokenizer import Token, TokenType
from parser import Node, NodeType


class ClassDef:
    def __init__(self, name):
        self.name = name
        self.attributes = {}
        self.methods = {}
    
    def __repr__(self):
        return f'ClassDef-{self.name}'

class ClassInstance:
    def __init__(self, class_def):
        self.class_name = class_def.name
        self.attribute_keys = class_def.attributes.keys()
        self.data = {}
    
    def __repr__(self):
        data = ",".join(str(k)+"="+str(self.data[k]) for k in self.attribute_keys)
        return f'{self.class_name}[{data}]'

class ReturnException(Exception):
    def __init__(self, value):
        self.value = value

class Evaluator:
    def __init__(self):
        self.env = {
            'true': True,
            'false': False,
            'nil': None,
        }
        self.frames = []
        self.classes = {}

    def evaluate(self, ast, scope=None):
        node_type = ast.type
        token = ast.token
        children = ast.children
        env = self.env if not scope else scope
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
                return env[token.value]
            case NodeType.FUNC_DEF:
                env[children[0].token.value] = ast
            case NodeType.RETURN:
                result = self.evaluate(children[0], scope)
                if not scope:
                    self.frames.pop()
                raise ReturnException(result)
            case NodeType.OPERATOR:
                if token.value == '=':
                    left = children[0]
                    right_val = self.evaluate(children[1], scope)
                    if left.type == NodeType.OPERATOR and left.token.value == '.':
                        instance = self.evaluate(left.children[0], scope)
                        instance.data[left.children[1].token.value] = right_val
                    else:
                        env[left.token.value] = right_val
                else:
                    left_val = self.evaluate(children[0], scope)
                    match token.value:
                        case '.':
                            if children[0].token.type==TokenType.NUM and children[1].token.type==TokenType.NUM:
                                return float(f'{left_val}.{self.evaluate(children[1], scope)}')
                            elif isinstance(left_val, ClassInstance):
                                if children[1].type == NodeType.IDENT:
                                    # memeber access
                                    return self.evaluate(children[1], scope=left_val.data)
                                elif children[1].type == NodeType.FUNC_CALL:
                                    # method access
                                    return self.class_method_call(left_val, children[1])
                            elif children[1].token.value == 'len':
                                return len(left_val)
                        case '=>':
                            func_node = Node(NodeType.FUNC_DEF, token)
                            func_node.children.append(Node(NodeType.IDENT, Token('(lambda)', TokenType.IDN, token.line, token.column)))
                            func_node.children.append(children[0])
                            func_node.children.append(children[1])
                            return func_node
                            
                    right_val = self.evaluate(children[1], scope)
                    match token.value:
                        case '+':
                            if children[0].token.type==TokenType.NUM and children[1].token.type==TokenType.NUM:
                                return float(left_val) + float(right_val)
                            try:
                                return left_val + right_val
                            except:
                                return str(left_val) + str(right_val)
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
                return [self.evaluate(expr, scope) for expr in children]
            case NodeType.STMT_LIST:
                result = None
                try:
                    for stmt in ast.children:
                        result = self.evaluate(stmt, scope)
                except ReturnException as e:
                    return e.value
                return result
            case NodeType.FUNC_CALL:
                params = []
                if children:
                    params = self.evaluate(children[0], scope)
                if token.value == 'print':
                    print(*params)
                elif token.value == 'type':
                    return str(type(params[0]).__name__)
                else:
                    func = env[token.value]
                    if isinstance(func, ClassDef):
                        # class constructor
                        return self.init_class_instance(func, params)
                    else:
                        # user defined function call
                        frame = {}
                        for i, arg in enumerate(func.children[1].children):
                            frame[arg.token.value] = params[i]
                        self.frames.append(frame)
                        return self.evaluate(func.children[2], scope)
            case NodeType.IF:
                condition_index = 0
                while condition_index < len(children) // 2:
                    cond = self.evaluate(children[condition_index * 2], scope)
                    if cond:
                        return self.evaluate(children[condition_index * 2 + 1], scope)
                    condition_index += 1
            case NodeType.FOR:
                var = children[0].children[0].token.value
                val_range = self.evaluate(children[0].children[1], scope)
                body = children[1]
                this_frame = {}
                self.frames.append(this_frame)
                result = None
                for val in val_range:
                    this_frame[var] = val
                    result = self.evaluate(body, scope)
                self.frames.pop()
                return result
            case NodeType.CLASS:
                env[children[0].token.value] = self.eval_class_def(ast)

    def eval_class_def(self, ast):
        data = ClassDef(ast.children[0].token.value)
        for stmt in ast.children[1].children:
            match stmt.type:
                case NodeType.OPERATOR:
                    if stmt.token.value == '=':
                        left = stmt.children[0].token.value
                        right = self.evaluate(stmt.children[1])
                        data.attributes[left] = right
                case NodeType.FUNC_DEF:
                    data.methods[stmt.children[0].token.value] = stmt
        return data

    def init_class_instance(self, class_def, params):
        instance = ClassInstance(class_def)
        # init attributes
        for k, v in class_def.attributes.items():
            instance.data[k] = v
        instance.data['this'] = instance

        # call init method (optional)
        if 'init' in class_def.methods:
            self.class_method_run(class_def, instance, 'init', params)
        return instance

    def class_method_call(self, class_instance, func_call):
        class_def = self.env[class_instance.class_name]
        method_name = func_call.token.value
        params = []
        if func_call.children:
            params = self.evaluate(func_call.children[0])
        return self.class_method_run(class_def, class_instance, method_name, params)

    def class_method_run(self, class_def, instance, method_name, params):
        method = class_def.methods[method_name]
        args = method.children[1].children
        method_body = method.children[2]

        for i, arg in enumerate(args):
            # TODO add method args to frame instead
            instance.data[arg.token.value] = params[i]

        return self.evaluate(method_body, scope=instance.data)