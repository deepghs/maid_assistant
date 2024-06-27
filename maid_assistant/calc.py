import ast
import math
import operator

# 允许的运算符
allowed_operators = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv
}

# 允许的数学函数
allowed_math_functions = {
    name: getattr(math, name)
    for name in dir(math) if callable(getattr(math, name))
}


def safe_eval(expr):
    node = ast.parse(expr, mode='eval').body

    def eval_(node):
        if isinstance(node, ast.Num):  # number
            return node.n
        elif isinstance(node, ast.Str):  # string
            return node.s
        elif isinstance(node, ast.BinOp):  # binary operator
            if type(node.op) in allowed_operators:
                return allowed_operators[type(node.op)](eval_(node.left), eval_(node.right))
            else:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        elif isinstance(node, ast.UnaryOp):  # unary operator
            if isinstance(node.op, ast.USub):
                return -eval_(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +eval_(node.operand)
            else:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        elif isinstance(node, ast.Call):  # function call
            if node.func.id in allowed_math_functions:
                func = allowed_math_functions[node.func.id]
                arg = eval_(*node.args)
                return func(arg)
            else:
                raise ValueError(f"Unsupported function call: {node.func.id}")
        else:
            raise ValueError(f"Not allowed expression type - {type(node).__name__}")

    return eval_(node)


if __name__ == '__main__':
    expression = "3 + 5 * (10 - 6) / 2 ** 2 + sin(3.14)"
    result = safe_eval(expression)
    print(f"Result: {result}")
