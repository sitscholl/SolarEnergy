from jinja2 import Environment, FileSystemLoader
import datetime

# Sample data
data = {
    'report_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'location': 'Example Location',
    'total_energy': 1234.56,
    'panels': {
        'south': {
            'area': 10.0,
            'offset': 7,
            'slope': 15,
            'aspect': 270,
            'efficiency': 0.15,
            'system_loss': 0.8
        },
        'east': {
            'area': 8.0,
            'offset': 5,
            'slope': 10,
            'aspect': 90,
            'efficiency': 0.16,
            'system_loss': 0.75
        }
    },
    'monthly_plot_url': 'images/monthly_energy_plot.png',  # Path to your plot image
    'panel_energy_totals': {
        'south': 1250.5,
        'east': 980.3,
        'west': 1100.8
    },
    "energy_metrics": {
        'Total Energy Produced': (1234.56, 'kWh'),
        'Average Daily Output': (3.38, 'kWh'),
        'Peak Power Output': (2.5, 'kW'),
        'Performance Ratio': (0.82, ''),
        'CO₂ Savings': (650, 'kg')
    }
}



# Configure Jinja2 environment
env = Environment(loader=FileSystemLoader('templates/'))  # Assumes templates are in the same directory
template = env.get_template('main_template.html')

# Render the template with the data
output = template.render(data)

# Save the output to an HTML file
with open('data/reports/report.html', 'w', encoding='utf-8') as f:
    f.write(output)

print("Report generated successfully!")