pep8:
	autopep8 -i *.py

stat:
	ansible -i ~/svs.txt all -m shell -a 'gpustat'

stat_day:
	ansible -i ~/svs.txt all -m shell -a '~/anaconda3/bin/python3 gpuwatch.py stat -s day'

plot_week:
	ansible -i ~/svs.txt all -m shell -a '~/anaconda3/bin/python3 gpuwatch.py stat -s week --plot'

fetch_svg:
	ansible -i ~/svs.txt all -m fetch -a "src=~/gpuwatch.svg dest={{inventory_hostname}}/ flat=yes"

fetch_db:
	ansible -i ~/svs.txt all -m fetch -a "src=~/__gpuwatch__.db dest={{inventory_hostname}}/ flat=yes"

copy_py:
	ansible -i ~/svs.txt all -m copy -a "src=gpuwatch.py dest=~/gpuwatch.py"
