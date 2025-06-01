"""
Configuration module using Pydantic for validation of config.yaml settings.
"""

from typing import List, Optional, Dict, Any, Union
from pathlib import Path
import yaml
from pydantic import BaseModel, Field, validator, root_validator
from datetime import datetime


class ConsumptionConfig(BaseModel):
    """Configuration for power consumption data."""
    consumption_tbl: str = Field(..., description="Path to power consumption Excel file")
    
    @validator('consumption_tbl')
    def validate_consumption_file(cls, v):
        """Validate that the consumption file path is provided."""
        if not v:
            raise ValueError("consumption_tbl path cannot be empty")
        return v


class OptimizationConfig(BaseModel):
    """Configuration for optimization parameters."""
    optim_dir: str = Field(..., description="Directory for optimization files")
    optim_coords: str = Field(..., description="Path to optimization coordinates shapefile")
    optim_file: str = Field(..., description="Path to optimization result CSV file")
    
    @validator('optim_dir', 'optim_coords', 'optim_file')
    def validate_paths(cls, v):
        """Validate that paths are not empty."""
        if not v:
            raise ValueError("Path cannot be empty")
        return v


class PanelConfig(BaseModel):
    """Configuration for solar panel parameters."""
    area: float = Field(ge=0, description="Panel area in square meters")
    offset: float = Field(description="Panel offset")
    slope: float = Field(ge=0, le=90, description="Panel slope in degrees")
    aspect: float = Field(ge=0, le=360, description="Panel aspect in degrees")
    efficiency: float = Field(ge=0, le=1, description="Panel efficiency (0-1)")
    system_loss: float = Field(ge=0, le=1, description="System loss factor (0-1)")


class PanelsConfig(BaseModel):
    """Configuration for all panel orientations."""
    south: PanelConfig


class FeatureSolarRadiationConfig(BaseModel):
    """Configuration for solar radiation feature calculation."""
    out_table_dir: str = Field(..., description="Path to the output directory for radiation analysis")
    unique_id_field: str = Field(default="ID", description="Unique identifier field name")
    time_zone: str = Field(default="UTC", description="Time zone for calculations")
    start_date_time: str = Field(..., description="Start date and time")
    end_date_time: str = Field(..., description="End date and time")
    interval_unit: str = Field(default="DAY", description="Time interval unit")
    interval: int = Field(default=1, ge=1, description="Time interval value")
    diffuse_model_type: str = Field(default="UNIFORM_SKY", description="Diffuse model type")
    diffuse_proportion: float = Field(ge=0, le=1, description="Diffuse proportion (0-1)")
    transmittivity: float = Field(ge=0, le=1, description="Atmospheric transmittivity (0-1)")
    
    @validator('start_date_time', 'end_date_time')
    def validate_date_format(cls, v):
        """Validate date format."""
        try:
            # Try to parse the date to ensure it's valid
            datetime.strptime(v, "%m/%d/%Y")
        except ValueError:
            raise ValueError(f"Date must be in MM/DD/YYYY format, got: {v}")
        return v


class FormatterConfig(BaseModel):
    """Configuration for log formatters."""
    format: str = Field(..., description="Log format string")
    datefmt: Optional[str] = Field(None, description="Date format string")


class HandlerConfig(BaseModel):
    """Configuration for log handlers."""
    class_: str = Field(..., alias="class", description="Handler class")
    formatter: str = Field(..., description="Formatter name")
    level: str = Field(..., description="Log level")
    stream: Optional[str] = Field(None, description="Stream for console handler")
    filename: Optional[str] = Field(None, description="Filename for file handler")
    mode: Optional[str] = Field(None, description="File mode")
    encoding: Optional[str] = Field(None, description="File encoding")
    maxBytes: Optional[int] = Field(None, description="Maximum bytes for rotating file")
    backupCount: Optional[int] = Field(None, description="Number of backup files")


class LoggerConfig(BaseModel):
    """Configuration for loggers."""
    handlers: List[str] = Field(..., description="List of handler names")
    level: str = Field(..., description="Log level")


class LoggingConfig(BaseModel):
    """Configuration for logging system."""
    version: int = Field(default=1, description="Logging config version")
    disable_existing_loggers: bool = Field(default=False, description="Disable existing loggers")
    formatters: Dict[str, FormatterConfig] = Field(..., description="Log formatters")
    handlers: Dict[str, HandlerConfig] = Field(..., description="Log handlers")
    loggers: Dict[str, LoggerConfig] = Field(..., description="Logger configurations")


class Config(BaseModel):
    """Main configuration class for the application."""
    location: List[float] = Field(..., min_items=2, max_items=2, description="Geographic coordinates [x, y]")
    crs: int = Field(..., description="Coordinate reference system EPSG code")
    dem: str = Field(..., description="Path to digital elevation model file")
    price: float = Field(gt=0, description="Energy price in ct/kWh")
    template_dir: str = Field(..., description="Directory for templates")
    report_out: str = Field(..., description="Directory for report output")
    output_directory: Optional[str] = Field(None, description="Optional output directory")
    
    consumption: ConsumptionConfig
    optimization: OptimizationConfig
    panels: PanelsConfig
    FeatureSolarRadiation: FeatureSolarRadiationConfig
    logging: LoggingConfig
    
    @validator('location')
    def validate_location(cls, v):
        """Validate location coordinates."""
        if len(v) != 2:
            raise ValueError("Location must contain exactly 2 coordinates [x, y]")
        if not all(isinstance(coord, (int, float)) for coord in v):
            raise ValueError("Location coordinates must be numeric")
        return v
    
    @validator('crs')
    def validate_crs(cls, v):
        """Validate CRS code."""
        if v <= 0:
            raise ValueError("CRS code must be positive")
        return v
    
    @validator('dem', 'template_dir', 'report_out')
    def validate_required_paths(cls, v):
        """Validate that required paths are not empty."""
        if not v or not v.strip():
            raise ValueError("Path cannot be empty")
        return v.strip()
    
    class Config:
        """Pydantic configuration."""
        allow_population_by_field_name = True
        validate_assignment = True


def load_config(config_path: Union[str, Path] = "config.yaml") -> Config:
    """
    Load and validate configuration from YAML file.
    
    Args:
        config_path: Path to the configuration YAML file
        
    Returns:
        Validated Config object
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML parsing fails
        ValidationError: If configuration validation fails
    """
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config_data = yaml.safe_load(file)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Error parsing YAML file: {e}")
    
    if config_data is None:
        raise ValueError("Configuration file is empty or invalid")
    
    return Config(**config_data)

# Example usage and validation
if __name__ == "__main__":
    try:
        config = load_config()
        print("Configuration loaded and validated successfully!")
        print(f"Location: {config.location}")
        print(f"CRS: {config.crs}")
        print(f"DEM file: {config.dem}")
        print(f"Price: {config.price} ct/kWh")
        print(f"Optimization enabled: {config.optimization.optimize_params}")
        print(f"Panel efficiency: {config.panels.south.efficiency}")
    except Exception as e:
        print(f"Configuration validation failed: {e}")