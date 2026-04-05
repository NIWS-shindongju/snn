"""SpikeEO command-line interface.

Usage:
    spikeeo run <input.tif> --task classification --classes 10
    spikeeo change <before.tif> <after.tif>
    spikeeo benchmark <test_dir/>
    spikeeo serve
    spikeeo info
"""

import logging
import sys

import click

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(package_name="spikeeo")
def main() -> None:
    """SpikeEO -- Energy-efficient satellite image analysis engine."""


@main.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--task", "-t", default="classification", show_default=True,
              type=click.Choice(["classification", "detection", "change_detection",
                                  "segmentation", "anomaly"]),
              help="Inference task type.")
@click.option("--classes", "-c", default=2, show_default=True, help="Number of output classes.")
@click.option("--bands", "-b", default=10, show_default=True, help="Number of input spectral bands.")
@click.option("--output", "-o", default=None, help="Output directory (default: ./results/).")
@click.option("--format", "-f", "fmt", default="geojson", show_default=True,
              type=click.Choice(["geojson", "json", "csv"]),
              help="Output format.")
@click.option("--weights", "-w", default=None, help="Path to pretrained weights.")
@click.option("--no-hybrid", is_flag=True, default=False, help="Disable SNN+CNN hybrid routing.")
def run(
    input_path: str,
    task: str,
    classes: int,
    bands: int,
    output: str | None,
    fmt: str,
    weights: str | None,
    no_hybrid: bool,
) -> None:
    """Run SNN inference on a GeoTIFF file."""
    import spikeeo
    from pathlib import Path

    out_dir = output or "./results"
    engine = spikeeo.Engine(
        task=task,
        num_classes=classes,
        num_bands=bands,
        use_hybrid=not no_hybrid,
        weights_path=weights,
    )
    result = engine.run(input_path, output_dir=out_dir, output_format=fmt)
    click.echo(f"Inference complete. Output written to {out_dir}/")
    if "cost_report" in result:
        cr = result["cost_report"]
        click.echo(f"Cost saving: {cr.get('cost_saving_pct', 0):.1f}%")


@main.command()
@click.argument("before_path", type=click.Path(exists=True))
@click.argument("after_path", type=click.Path(exists=True))
@click.option("--output", "-o", default="./results", show_default=True, help="Output directory.")
def change(before_path: str, after_path: str, output: str) -> None:
    """Detect changes between two GeoTIFF acquisitions."""
    import spikeeo

    engine = spikeeo.Engine(task="change_detection")
    result = engine.run_change(before_path, after_path, output_dir=output)
    click.echo(f"Change detection complete. Output written to {output}/")
    if "change_stats" in result:
        stats = result["change_stats"]
        click.echo(f"Changed area: {stats.get('change_area_ha', 0):.2f} ha")


@main.command()
@click.argument("test_dir", type=click.Path(exists=True))
@click.option("--cnn", default="resnet18", show_default=True, help="CNN baseline model.")
@click.option("--output", "-o", default="benchmark_report.json", help="Output JSON file.")
@click.option("--classes", "-c", default=2, show_default=True, help="Number of output classes.")
@click.option("--bands", "-b", default=10, show_default=True, help="Number of input bands.")
def benchmark(test_dir: str, cnn: str, output: str, classes: int, bands: int) -> None:
    """Benchmark SNN vs CNN on test data."""
    import json
    import spikeeo

    engine = spikeeo.Engine(task="classification", num_classes=classes, num_bands=bands)
    report = engine.benchmark(test_data_dir=test_dir, cnn_model=cnn)

    import json
    with open(output, "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    click.echo(f"Benchmark report saved to {output}")
    click.echo(f"SNN accuracy:  {report.get('snn_accuracy', 0):.3f}")
    click.echo(f"CNN accuracy:  {report.get('cnn_accuracy', 0):.3f}")
    click.echo(f"Cost saving:   {report.get('cost_saving_estimate_pct', 0):.1f}%")


@main.command()
@click.option("--host", default="0.0.0.0", show_default=True, help="Bind host.")
@click.option("--port", default=8000, show_default=True, help="Bind port.")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload.")
def serve(host: str, port: int, reload: bool) -> None:
    """Start the SpikeEO REST API server."""
    try:
        import uvicorn
    except ImportError:
        click.echo("uvicorn not found. Install with: pip install spikeeo[api]", err=True)
        sys.exit(1)

    uvicorn.run(
        "spikeeo.api.server:app",
        host=host,
        port=port,
        reload=reload,
    )


@main.command()
def info() -> None:
    """Display SpikeEO version and environment information."""
    import spikeeo
    import torch
    import platform

    click.echo(f"SpikeEO version:  {spikeeo.__version__}")
    click.echo(f"Python:           {platform.python_version()}")
    click.echo(f"PyTorch:          {torch.__version__}")
    cuda = torch.cuda.is_available()
    click.echo(f"CUDA available:   {cuda}")
    if cuda:
        click.echo(f"CUDA device:      {torch.cuda.get_device_name(0)}")
    click.echo(f"Supported tasks:  {', '.join(spikeeo.engine.SUPPORTED_TASKS)}")
