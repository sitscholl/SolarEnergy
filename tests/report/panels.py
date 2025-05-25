from jinja2 import Environment, FileSystemLoader
import yaml
from pathlib import Path
from datetime import datetime

with open("config.yaml", 'r') as f:
    config = yaml.safe_load(f)

environment = Environment(loader=FileSystemLoader("templates/"))
template = environment.get_template("panels.html")
content = template.render(panels = config['panels'])

out_report = Path("data", "reports", f'panels_{datetime.now():%Y_%m_%d_%H%M%S}.html')
with open(out_report, mode="w", encoding="utf-8") as report:
    report.write(content)