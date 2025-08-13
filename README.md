# India Stray Dogs Map 2019

A comprehensive visualization of stray dog population density across Indian states and union territories based on 2019 data from the Department of Animal Husbandry and Dairying (DAHD).

![Stray Dogs per 1000 People - India 2019](outputs/stray_dogs_per_1000_2019.png)

## Overview

This project creates a choropleth map showing the number of stray dogs per 1000 people across India's states and union territories. The visualization combines official government data on stray dog counts with population projections to provide insights into animal welfare challenges across the country.

## Key Features

- **State-wise Analysis**: Individual data for all 34 states and union territories
- **Population Normalized**: Shows stray dogs per 1000 people for fair comparison
- **Professional Visualization**: Clean, publication-ready map with proper styling
- **Data Sources**: Uses official DAHD livestock census and MoHFW population projections
- **Automated Processing**: Downloads and processes data automatically

## Data Sources

- **Stray Dog Counts**: Ministry of Fisheries, Animal Husbandry and Dairying (DAHD)
  - 20th Livestock Census, 2019
  - Source: [DAHD Official Website](https://dahd.nic.in/)
- **Population Data**: Ministry of Health and Family Welfare (MoHFW)
  - Population Projections 2011-2036 Report
- **Geographic Boundaries**: State boundaries from open geographic data sources

## Key Findings

- **Highest Density**: Odisha (37.4 per 1000), Jammu & Kashmir (23.4 per 1000)
- **Lowest Density**: Mizoram (0.1 per 1000), Nagaland (0.2 per 1000)
- **National Average**: ~11 stray dogs per 1000 people
- **Regional Patterns**: Higher concentrations in certain northern and eastern states

## Installation & Usage

### Prerequisites

```bash
Python 3.8+
```

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/india-stray-dogs-map.git
cd india-stray-dogs-map
```

2. Create virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### Run the Analysis

```bash
python make_stray_dog_map.py
```

This will:
- Download the latest DAHD Excel data
- Download Indian state boundaries
- Process and merge the datasets
- Generate the visualization and CSV output

### Outputs

- `outputs/stray_dogs_per_1000_2019.png` - High-resolution map visualization
- `outputs/stray_dogs_per_1000_2019.csv` - Processed state-wise data

## Dependencies

- `pandas>=2.0` - Data manipulation and analysis
- `geopandas>=0.14` - Geographic data processing
- `matplotlib>=3.7` - Visualization and plotting
- `requests>=2.31` - Data downloading
- `pyogrio>=0.7` - Fast geographic file I/O
- `openpyxl` - Excel file reading

## Project Structure

```
india-stray-dogs-map/
├── make_stray_dog_map.py      # Main analysis script
├── requirements.txt           # Python dependencies
├── data/                      # Downloaded data files
│   ├── FinalDistrictWiseStrayCattleDog.xlsx
│   ├── india_states.geojson
│   └── pop_projection_2019.csv
├── outputs/                   # Generated outputs
│   ├── stray_dogs_per_1000_2019.png
│   └── stray_dogs_per_1000_2019.csv
└── README.md                  # This file
```

## Methodology

1. **Data Collection**: Automatically downloads DAHD livestock census data
2. **Data Processing**: 
   - Extracts state-wise stray dog counts
   - Standardizes state names across datasets
   - Handles union territory mergers (e.g., Dadra & Nagar Haveli and Daman & Diu)
3. **Population Normalization**: Calculates dogs per 1000 people using 2019 projections
4. **Visualization**: Creates choropleth map with proper color scaling and labels

## Technical Details

- **Coordinate System**: WGS84 (EPSG:4326)
- **Color Scheme**: Pink-Red gradient (RdPu colormap)
- **Resolution**: 300 DPI for publication quality
- **Format**: PNG with transparent background support

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Department of Animal Husbandry and Dairying (DAHD) for providing livestock census data
- Ministry of Health and Family Welfare for population projection data
- Open geographic data contributors for state boundary data

## Author

**Naveen Srinivas**

---

*This visualization aims to support evidence-based policy making for animal welfare and public health initiatives across India.*
