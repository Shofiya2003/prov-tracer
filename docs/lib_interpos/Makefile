prov_example.svg: prov_example.dot
	dot prov_example.dot -Tsvg -o prov_example.svg

feature_matrix.tex: feature_matrix.py
	./feature_matrix.py

README.tex: README.md prov_example.svg feature_matrix.tex
	pandoc --template=../usenix_template.tex --filter=pandoc-crossref  --citeproc --biblatex -i README.md -o README.tex


README.pdf: README.tex
	env TEXINPUTS=$$(dirname $$PWD)//: pdflatex -interaction=nonstopmode -shell-escape README || true
	biber README
	env TEXINPUTS=$$(dirname $$PWD)//: pdflatex -interaction=nonstopmode -shell-escape README

re-README.pdf:
	touch README.tex README.pdf
	rm README.tex README.pdf
	make README.pdf

#env TEXINPUTS=$(dirname $PWD)//: latexmk -interaction=nonstopmode -shell-escape -pdf -shell-escape -emulate-aux-dir -Werror README
