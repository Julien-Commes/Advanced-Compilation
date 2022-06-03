from operator import indexOf
import lark

grammaire = lark.Lark("""
variables : IDENTIFIANT (","  IDENTIFIANT)*
expr : IDENTIFIANT -> variable | NUMBER -> nombre | expr OP expr -> binexpr | "(" expr ")" -> parenexpr | IDENTIFIANT "(" (expr ",")* expr ")" -> call_function | IDENTIFIANT "(" ")" -> call_function_no_arg | "'" string "'" -> str | "'" "'" -> empty_str | element -> elt | "new" tableau -> tbl 
cmd : IDENTIFIANT "=" expr ";"-> assignment|"while" "(" expr ")" "{" bloc "}" -> while | "if" "(" expr ")" "{" bloc "}" -> if | "printf" "(" expr ")" ";"-> printf | element "=" expr ";" -> assignement_tableau
bloc : (cmd)*
prog : functions "main" "(" variables ")" "{" bloc "return" "(" expr ")" ";" "}"
functions : function*
function : IDENTIFIANT "(" variables ")" "{" bloc "return" "(" expr ")" ";" "}"
string : /[a-zA-Z0-9][a-zA-Z0-9]*/
tableau : "int" "[" expr "]"
element : IDENTIFIANT "[" expr "]"  
NUMBER : /[0-9]+/
OP : /[+\*>-]/
IDENTIFIANT : /[a-zA-Z][a-zA-Z0-9]*/
%import common.WS
%ignore WS
""", start = "prog")

cpt = iter(range(10000))
op2asm = {"+" : "add rax, rbx","-" : "sub rax, rbx"}

########################################## Pretty Printer ##############################################################

def pp_variables(vars):
    return ", ".join([t.value for t in vars.children])


def pp_expr(expr):
    if expr.data in {"variable", "nombre"}:
        return expr.children[0].value
    elif expr.data == "binexpr":
        e1 = pp_expr(expr.children[0])
        e2 = pp_expr(expr.children[2])
        op = expr.children[1].value
        return f"{e1} {op} {e2}"
    elif expr.data == "parenexpr":
        return f"({pp_expr(expr.children[0])})"
    elif expr.data == "call_function":
        nom = expr.children[0]
        vars = ", ".join([pp_expr(ex) for ex in expr.children[1:]])
        return f"{nom} ({vars})"
    elif expr.data == "call_function_no_arg":
        nom = expr.children[0]
        return f"{nom} ()"
    elif expr.data=="str":
        return(pp_string(expr.children[0]))
    elif expr.data=="empty_str":
        return "''"
    elif expr.data=="tbl":
        return(f"new {pp_tableau(expr.children[0])}")
    elif expr.data=="elt":
        return(pp_element(expr.children[0]))
    else:
        raise Exception("Not implemented")


def pp_cmd(cmd):
    if cmd.data == "assignment":
        lhs = cmd.children[0].value
        rhs = pp_expr(cmd.children[1])
        return f"{lhs} = {rhs};"
    elif cmd.data == "printf":
        return f"printf( {pp_expr(cmd.children[0])} );"
    elif cmd.data in {"while", "if"}:
        e = pp_expr(cmd.children[0])
        b = pp_bloc(cmd.children[1])
        return f"{cmd.data} ({e}) {{ {b}}}"
    elif cmd.data=="assignement_tableau":
        element=pp_element(cmd.children[0])
        valeur=pp_expr(cmd.children[1])
        return f"{element}={valeur};"
    else:
        raise Exception("Not implemented")


def pp_bloc(bloc):
    return "\n".join([pp_cmd(t) for t in bloc.children])

def pp_function(f):
    nom = f.children[0]
    vars = pp_variables(f.children[1])
    bloc = pp_bloc(f.children[2])
    ret = pp_expr(f.children[3])
    return f"{nom} ({vars}){{ {bloc} return ({ret});}}"

def pp_string(s):
    nom = s.children[0]
    return f"'{nom}'"

def pp_tableau(T):
    taille=pp_expr(T.children[0])
    return f"int [{taille}]"

def pp_element(e):
    nom=e.children[0]
    indice=pp_expr(e.children[1])
    return f"{nom}[{indice}]"

def pp_prg(prog):
    functions="\n\n".join([pp_function(f) for f in prog.children[0].children])
    vars = pp_variables(prog.children[1])
    bloc = pp_bloc(prog.children[2])
    ret = pp_expr(prog.children[3])
    return f"{functions}\n\nmain ({vars}){{ {bloc} return ({ret});}}"

def var_list(ast):
    if isinstance(ast, lark.Token):
        if ast.type == "IDENTIFIANT":
            return {ast.value}
        else:
            return set()
    s = set()
    for c in ast.children:
        if (isinstance(c, lark.Tree) and c.data=="call_function"):
            for a in c.children[1:]:
                s.update(var_list(a))
        else:
            s.update(var_list(c))
    return s


############################################### COMPILE ###############################################################################

def compile(prg):
    with open("moule.asm") as f:
        code = f.read()
        vars_decl =  "\n".join([f"{x} : dq 0" for x in var_list(prg.children[2])|var_list(prg.children[1])])
        code = code.replace("VAR_DECL", vars_decl)
        code = code.replace("FUNCTIONS", compile_functions(prg.children[0]))
        code = code.replace("RETURN", compile_expr(prg.children[3]))
        code = code.replace("BODY", compile_bloc(prg.children[2]))
        code = code.replace("VAR_INIT", compile_vars(prg.children[1]))
    with open("prgm.asm",'w') as f:
          f.write(code)    
    return code

def compile_functions(functions):
    return "\n".join([compile_function(x) for x in functions.children])

def compile_function(function):
    ens_var_input=var_list(function.children[1])
    ens_all_var=var_list(function.children[2])
    ens_local_var=ens_all_var.difference(ens_var_input)
    list_var_input=[var.value for var in function.children[1].children]
    list_local_var=[var for var in ens_local_var]
    res=f"{function.children[0]}:\npush rbp\nmov rbp,rsp\n"
    res+=compile_bloc_for_function(function.children[2],list_local_var,list_var_input)+"\n"
    res+=compile_expr_for_function(function.children[3],list_local_var,list_var_input)+"\n"
    res+= "mov rsp,rbp\npop rbp\nret"
    return res

def compile_expr(expr):
    if expr.data == "variable":
        return f"mov rax, [{expr.children[0].value}]"
    elif expr.data == "nombre":
        return f"mov rax, {expr.children[0].value}"
    elif expr.data == "binexpr":
        e1 = compile_expr(expr.children[0])
        e2 = compile_expr(expr.children[2])
        op = expr.children[1].value
        return f"{e2}\npush rax\n{e1}\npop rbx\n{op2asm[op]}"
    elif expr.data == "parenexpr":
        return compile_expr(expr.children[0])
    elif expr.data == "call_function":
        push_arg="\n".join([compile_expr(expr.children[i])+"\npush rax" for i in range(len(expr.children)-1,0,-1)])+"\n"
        call_function=f"call {expr.children[0]}"
        pop_arg=f"\nadd rsp,{8*(len(expr.children)-1)}"
        return  push_arg+call_function+pop_arg
    else:
        raise Exception("Not implemented")

def compile_cmd(cmd):
    if cmd.data == "assignment":
        lhs = cmd.children[0].value
        rhs = compile_expr(cmd.children[1])
        return f"{rhs}\nmov [{lhs}], rax"
    elif cmd.data == "while":
        e = compile_expr(cmd.children[0])
        b = compile_bloc(cmd.children[1])
        index = next(cpt)
        return f"debut{index}:\n{e}\ncmp rax, 0\njz fin{index}\n{b}\njmp debut{index}\nfin{index}:\n"
    else:
        raise Exception("Not implemented")


def compile_bloc(bloc):
    return "\n".join([compile_cmd(t) for t in bloc.children])

def compile_vars(ast):
    s = ""
    for i in range(len(ast.children)):
        s+= f"mov rbx, [rbp-0x10]\nmov rdi, [rbx+{8*(i+1)}]\ncall atoi\nmov [{ast.children[i].value}], rax\n"
    return s

######################### compile in function #########################
def compile_expr_for_function(expr,local_var,global_var):
    if expr.data == "variable":
        if (expr.children[0].value in local_var):
            return f"mov rax, [rbp-{local_var.index(expr.children[0].value)*8+8}]"
        elif (expr.children[0].value in global_var):
            return f"mov rax, [rbp+{global_var.index(expr.children[0].value)*8+16}]"
        else:
            raise Exception("Not var with this name")
    elif expr.data == "nombre":
        return f"mov rax, {expr.children[0].value}"
    elif expr.data == "binexpr":
        e1 = compile_expr_for_function(expr.children[0],local_var,global_var)
        e2 = compile_expr_for_function(expr.children[2],local_var,global_var)
        op = expr.children[1].value
        return f"{e2}\npush rax\n{e1}\npop rbx\n{op2asm[op]}"
    elif expr.data == "parenexpr":
        return compile_expr_for_function(expr.children[0],local_var,global_var)
    elif expr.data == "call_function":
        return f"call {expr.children[0]}"    
    else:
        raise Exception("Not implemented")

def compile_cmd_for_function(cmd,local_var,global_var):
    if cmd.data == "assignment":
        if (cmd.children[0].value in local_var):
            lhs = f"rbp-{local_var.index(cmd.children[0].value)*8+8}"
        elif (cmd.children[0].value in global_var):
            lhs = f"rbp+{global_var.index(cmd.children[0].value)*8+16}"
        else:
            raise Exception("Not var with this name")
        rhs = compile_expr_for_function(cmd.children[1],local_var,global_var)
        return f"{rhs}\nmov [{lhs}], rax"
    # elif cmd.data == "while":
    #     e = compile_expr(cmd.children[0])
    #     b = compile_bloc(cmd.children[1])
    #     index = next(cpt)
    #     return f"debut{index}:\n{e}\ncmp rax, 0\njz fin{index}\n{b}\njmp debut{index}\nfin{index}:\n"
    else:
        raise Exception("Not implemented")

def compile_bloc_for_function(bloc,local_var,global_var):
    return "\n".join([compile_cmd_for_function(t,local_var,global_var) for t in bloc.children])


if __name__ == "__main__":
    prg = grammaire.parse("""    
    f1(V,D){
        X=V+D;
        return (X);
    }
    
    main(X,D) {
        Y=f1(X,D);
        return(Y);}""")
    compile(prg)
