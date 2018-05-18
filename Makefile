AnswerNotebooks=$(wildcard */*-answers.ipynb)
StudentNotebooks=$(AnswerNotebooks:-answers.ipynb=.ipynb)

.PHONY: all studentNotebooks clean

all: $(StudentNotebooks)

clean:
	rm -rf $(StudentNotebooks)

%.ipynb: %-answers.ipynb
	@echo "Should close notebook $< before running this command"
	python3 add_cell_tracking.py --notebook $<
	python3 preprocess.py --input $< --output $@
