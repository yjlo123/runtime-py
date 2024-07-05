import os
from tokenizer import Token, TokenType, Tokenizer
from vee_parser import Node, NodeType, Parser


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

class Environment:
    def __init__(self, env, current, frames):
        self._global = env
        self._cur_scope = current
        self._frames = frames

    def get(self, name, token=None):
        # check function scope
        if self._frames and name in self._frames[-1]:
            return self._frames[-1][name]
        # check instance scope
        if self._cur_scope is not None and name in self._cur_scope:
            return self._cur_scope[name]
        # check global
        if name not in self._global:
            # print('frame: ', self._frames[-1].keys() if self._frames else None)
            # print('scope: ', self._cur_scope.keys() if self._cur_scope else None)
            # print('global: ', self._global.keys())
            msg = f'Undefined variable `{name}`' + (f' at {token.line}:{token.column}' if token else '')
            raise Exception(msg)
        return self._global[name]
    
    def set_global(self, name, value):
        self._global[name] = value

    def set(self, name, value):
        if self._cur_scope is None and len(self._frames) > 0:
            # function scope
            self._frames[-1][name] = value
        elif self._cur_scope is not None and len(self._frames) > 0 and name in self._frames[-1]:
            # method local overriding instance scope
            self._frames[-1][name] = value
        elif self._cur_scope is not None and name in self._cur_scope:
            # instance scope
            self._cur_scope[name] = value
        else:
            # global
            self._global[name] = value
    
    def print_env(self):
        print(">>>>", self._global, "|||||", self._cur_scope, "/////", self._frames)

class Evaluator:
    def __init__(self, src_file_name):
        self.src_file_name = src_file_name
        self.env = {
            'true': True,
            'false': False,
            'nil': None,
        }
        self.frames = []

    def evaluate(self, ast, scope=None):
        node_type = ast.type
        token = ast.token
        children = ast.children
        env = Environment(self.env, scope, self.frames)
        match node_type:
            case NodeType.VALUE:
                if token.type == TokenType.NUM:
                    if '.' in token.value:
                        return float(token.value)
                    else:
                        return int(token.value)
                return token.value
            case NodeType.IDENT:
                return env.get(token.value, token)
            case NodeType.FUNC_DEF:
                env.set_global(children[0].token.value, ast)
            case NodeType.RETURN:
                result = self.evaluate(children[0], scope)
                raise ReturnException(result)
            case NodeType.OPERATOR:
                left = children[0] if len(children) >= 1 else None
                right = children[1] if len(children) >= 2 else None
                if token.value == '=':
                    right_val = self.evaluate(right, scope)
                    if left.type == NodeType.OPERATOR and left.token.value == '.':
                        instance = self.evaluate(left.children[0], scope)
                        instance.data[left.children[1].token.value] = right_val
                    else:
                        env.set(left.token.value, right_val)
                else:
                    # operators not requiring eval left or right
                    match token.value:
                        case '=>':
                            func_node = Node(NodeType.FUNC_DEF, token)
                            func_node.children.append(Node(NodeType.IDENT, Token('(lambda)', TokenType.IDN, token.line, token.column)))
                            func_node.children.append(left)
                            func_node.children.append(right)
                            return func_node

                    # operators requiring left evaluated
                    left_val = self.evaluate(left, scope)
                    match token.value:
                        case '.':
                            if left.token.type==TokenType.NUM and right.token.type==TokenType.NUM:
                                return float(f'{left_val}.{self.evaluate(right, scope)}')
                            elif isinstance(left_val, ClassInstance):
                                if right.type == NodeType.IDENT:
                                    # memeber access
                                    return self.evaluate(right, scope=left_val.data)
                                elif right.type == NodeType.FUNC_CALL:
                                    # method access
                                    try:
                                        return self.class_method_call(left_val, right)
                                    except ReturnException as e:
                                        # capture method return
                                        return e.value
                            elif right.token.value == 'len':
                                return len(left_val)

                    # operators may not require right evaluated
                    match token.value:
                        case '&&':
                            if not left_val:
                                return False
                            return self.evaluate(right, scope)
                        case '||':
                            if not left_val:
                                return self.evaluate(right, scope)
                            return True

                    # operators requres right evaluated
                    right_val = self.evaluate(children[1], scope) if len(children) >= 2 else None
                    match token.value:
                        case '+':
                            if children[0].token.type==TokenType.NUM and children[1].token.type==TokenType.NUM:
                                return float(left_val) + float(right_val)
                            try:
                                return left_val + right_val
                            except:
                                return str(left_val) + str(right_val)
                        case '-':
                            if right_val == None:
                                return 0 - int(left_val)
                            return int(left_val) - int(right_val)
                        case '*':
                            return float(left_val) * float(right_val)
                        case '/.':
                            return float(left_val) / float(right_val)
                        case '/':
                            return left_val // right_val
                        case '%':
                            return left_val % right_val
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
                        case '!=':
                            return left_val != right_val
                        case '..':
                            return range(int(left_val), int(right_val))
                        case '[':
                            return left_val[int(right_val)]
                        case ':':
                            return (left_val, right_val)
                        case _:
                            raise SyntaxError(f'unhandled operator: {token}')
            case NodeType.EXPR_LIST:
                return [self.evaluate(expr, scope) for expr in children]
            case NodeType.STMT_LIST:
                result = None
                for stmt in ast.children:
                    result = self.evaluate(stmt, scope)
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
                    func = env.get(token.value, token)
                    if isinstance(func, ClassDef):
                        # class constructor
                        return self.init_class_instance(func, params)
                    else:
                        # user defined function call
                        frame = {}
                        for i, arg in enumerate(func.children[1].children):
                            frame[arg.token.value] = params[i]
                        self.frames.append(frame)
                        returned = None
                        try:
                            returned = self.evaluate(func.children[2], scope)
                        except ReturnException as e:
                            # capture function return
                            returned = e.value
                        self.frames.pop()
                        return returned
            case NodeType.IF:
                condition_index = 0
                while condition_index < len(children) // 2:
                    cond = self.evaluate(children[condition_index * 2], scope)
                    if cond:
                        return self.evaluate(children[condition_index * 2 + 1], scope)
                    condition_index += 1
            case NodeType.FOR:
                var = children[0].token.value
                val_range = self.evaluate(children[1], scope)
                body = children[2]
                this_frame = {}
                # TODO new frame? should be able to access local scope in function
                self.frames.append(this_frame)
                result = None
                for val in val_range:
                    this_frame[var] = val
                    result = self.evaluate(body, scope)
                self.frames.pop()
                return result
            case NodeType.WHILE:
                cond = children[0]
                body = children[1]
                result = None
                while self.evaluate(cond, scope):
                    result = self.evaluate(body, scope)
                return result
            case NodeType.CLASS:
                env.set_global(children[0].token.value, self.eval_class_def(ast))
            case NodeType.IMPORT:
                path = os.path.dirname(self.src_file_name)
                # TODO import from multi level path
                #      resolve dependencies
                file_name = children[0].children[0].token.value + '.vee'
                value_name = children[0].children[1].token.value
                file_path = os.path.join(path, file_name)
                with open(file_path, 'r') as src_file:
                    tokenizer = Tokenizer()
                    tokens = tokenizer.tokenize(src_file.read())
                    parser = Parser(tokens)
                    ast = parser.parse()
                    # ast.pretty_print(indent='', is_last=True)
                    evaluator = Evaluator(file_path)
                    evaluator.evaluate(ast)
                    self.env[value_name] = evaluator.env[value_name]
            case _:
                raise Exception(f'Unknown AST node type {node_type}')

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
            # when contructor is present
            if len(class_def.methods['init'].children[1].children) == len(params):
                # when argument count match
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

        frame = {}
        for i, arg in enumerate(args):
            frame[arg.token.value] = params[i]
        self.frames.append(frame)
        returned = self.evaluate(method_body, scope=instance.data)
        self.frames.pop()
        return returned
