pep8:
	autopep8 -i *.py

stat:
	ansible -i ~/svs.txt all -m shell -a 'gpustat'

all:
	$(MAKE) copy_py
	$(MAKE) fetch_db
	$(MAKE) plot_week
	$(MAKE) fetch_svg
	-evince svgreduce.pdf

stat_day:
	ansible -i ~/svs.txt all -m shell -a '~/anaconda3/bin/python3 gpuwatch.py stat -s day'

plot_week:
	ansible -i ~/svs.txt all -m shell -a "~/anaconda3/bin/python3 gpuwatch.py stat -s week --plot --plot_title '{{inventory_hostname}}'"

fetch_svg:
	ansible -i ~/svs.txt all -m fetch -a "src=~/gpuwatch.svg dest={{inventory_hostname}}_gpuwatch.svg flat=yes"
	python3 gpuwatch.py svgreduce 2>/dev/null
	@echo
	@echo Check svgreduce.pdf for the gathered plots.

fetch_db:
	ansible -i ~/svs.txt all -m fetch -a "src=~/__gpuwatch__.db dest={{inventory_hostname}}_gpuwatch.db flat=yes"

copy_py:
	ansible -i ~/svs.txt all -m copy -a "src=gpuwatch.py dest=~/gpuwatch.py"
