# Advanced-Compilation

Structure du dossier :
compilo.py
test1.nanoC (exemples bien choisis)
test2.nanoC
read.me
comment faire pour avoir un pp (ex : python3 compile.py pp test1.nanoC)
comment faire pour avoir une cp
 
linux
- librairie python lark (tokenizer : fichier texte.c -> liste de "tokens" (= élts atomiques de syntaxe : +, =, ℤ, while, ...) -> arbre de syntaxe abstrait -> génération de code (langage machine abstrait comme LLVM, puis traduction vers la machine cible) -> fichier texte.asm)
- nasm (texte.asm -> texte.o)
- gcc (texte.o -> a.out)


langage de programmation :
- instruction et communique avec le hardware / est implémenté sur une machine / permet de s'abstraire du code machine
- défini sur un alphabet
- respecte une grammaire
- mot, opérations
- ça sert à calculer
¤ syntaxe
¤ sémantique : dit ce que fait le programme

compilateur :
L1 = (Syn1, Sém1) ---> L2 = (Syn2, Sém2)


création d'un langage : 
- entiers relatifs ℤ (64 bits) -> ce qui est l'objet du calcul
- (booléens : ce seront des entiers, 0 ~ "false" et n≠0 ~ "true")
- opérations Op : +, -, *, //, %, **, <, ==
- variables : V = ensemble des variables
- instructions : while, if/else, affectation, printf
- point d'entrée
=> expressions Exp : ℤ | V | Exp Op Exp
=> commandes (= instructions) Com : V = Exp | while(Exp){Com} | if(Exp){Com} else{Com} | printf(Exp) | Com; Com
=> programme Prg : main(V,V,...){Com; return(Exp)}


définition mathématique de la sémantique du langage :
 
1. magasins
- un magasin (= store/valuation) est une fonction V ⟶ ℤ
- M = ensemble des magasins
¤  Ø : 	V ⟶ ℤ
	X ⟼ 0
¤  si m∈M, X∈V, n∈ℤ,  m[X<-n] :	V ⟶ ℤ
				Y ⟼ m(Y) si Y ≠ X
				X ⟼ n

2. sémantique dénotationnelle(∈opérationnelle∈axiomatique) 
- E∈Exp,  ⟦E⟧ : M ⟶ ℤ 	(⟦⟧ = crochets sémantiques)
¤ E = n∈ℤ : ⟦n⟧(m) = n
¤ E = x∈V : ⟦x⟧(m) = m(x)
¤ E = (E1 Op E2) : 
	⟦E1+E2⟧(m) = ⟦E1⟧(m) + ⟦E2⟧(m)
	⟦E1>E2⟧(m) = signe(⟦E1⟧(m) - ⟦E2⟧(m))	(avec signe(x) = max(0,x))
- C∈Com,  ⟦C⟧ : M ⟶ M
¤ C = (X=E) :
	⟦C⟧(m) = m[X<-⟦E⟧(m)]
¤ C = printf(E) :
	⟦C⟧(m) = m
¤ C = if(E){C'} :
	⟦C⟧(m) = ⟦C'⟧(m) 	si ⟦E⟧(m) ≠ Ø
		m 	sinon
¤ C = while(E){C'} :
	⟦C⟧(m) = ⟦C⟧(⟦C'⟧(m)) 	si ⟦E⟧(m) ≠ Ø
		m 		sinon
¤ C = C1; C2 :
	⟦C⟧(m) = ⟦C2⟧(⟦C1⟧(m)) 
- P = main(X1,...,Xk){C; return(E)},     ⟦P⟧ : 	ℤ^k ⟶ ℤ
 						(x1,...,xk) ⟼ ⟦E⟧(⟦C⟧(Ø[X1<-x1]...[Xk<-xk]))

compilo.py

helloworld.asm :

extern printf
global main

section .data
hello : 
	db "Hello world", 10, 0 ; db = data byte, dw = word = 2 octets, dd = dword = 4 octets (int en C), dq = quad word = 8 octets | 10 ~ "\n" | le 0 est nécessaire pour printf car c'est formaté comme ça en C

section .text
main :
mov rsi,12 ; rsi=12 , "registre=immédiat"
; mov 12,%rsi si autre que intel
mov rdi, hello
xor rax, rax ; on doit mettre rax à 0 pour pouvoir utiliser rdi (et faire un xor rax,rax est moins coûteux en mémoire qu'un mov rax,0)
call printf
ret
; les registres (1 registre = 8 octets) : rax,rbx,rcx,rdx,rsi,rdi,r8,...,r15 | ordre = rax : 0, rdi : 1 arg, rsi : 2 arg, rcx, rdx, r8, r9, pile. | al = 1er octet de rax, ah = 2e octet de rax, ax = 2 premiers octets de rax, eax = 4 premiers octets de rax
; cf photo 11 mai pour toutes les commandes


dans le terminal : nasm -f elf64 helloworld.asm
=> helloworld.o
puis : gcc -no-pie -fno-pie helloworld.o
=> a.out