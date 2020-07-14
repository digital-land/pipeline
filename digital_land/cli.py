import sys
import os
import click
import logging
import tempfile
from . import generate
from .load import load, load_csv, load_csv_dict
from .collect import Collector
from .index import Indexer
from .save import save
from .normalise import Normaliser
from .issues import Issues, IssuesFile
from .harmonise import Harmoniser
from .transform import Transformer
from .resource_organisation import ResourceOrganisation
from .organisation import Organisation
from .map import Mapper
from .schema import Schema


@click.group()
@click.option("-d", "--debug/--no-debug", default=False)
def cli(debug):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")


@cli.command("fetch")
@click.argument("url")
def fetch_cmd(url):
    """fetch a single source endpoint URL, and add it to the collection"""
    collector = Collector()
    collector.fetch(url)


@cli.command("collect")
@click.argument(
    "endpoint_path", type=click.Path(exists=True), default="collection/endpoint.csv",
)
def collect_cmd(endpoint_path):
    """fetch the sources listed in the endpoint-url column of the ENDPOINT_PATH CSV file"""
    collector = Collector()
    collector.collect(endpoint_path)


@cli.command("convert", short_help="convert to a well-formed, UTF-8 encoded CSV file")
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
def convert_cmd(input_path, output_path):
    reader = load(input_path)
    if not reader:
        logging.error(f"Unable to convert {input_path}")
        sys.exit(2)
    save(reader, output_path)


@cli.command("normalise", short_help="removed padding, drop empty rows")
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
@click.option(
    "--null-path",
    type=click.Path(exists=True),
    help="patterns for null fields",
    default=None,
)
@click.option(
    "--skip-path",
    type=click.Path(exists=True),
    help="patterns for skipped lines",
    default=None,
)
def normalise_cmd(input_path, output_path, null_path, skip_path):
    normaliser = Normaliser(null_path=null_path, skip_path=skip_path)
    stream = load_csv(input_path)
    stream = normaliser.normalise(stream)
    save(stream, output_path)


@cli.command("map", short_help="map misspelt column names to those in a schema")
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
@click.argument("schema_path", type=click.Path(exists=True))
def map_cmd(input_path, output_path, schema_path):
    schema = Schema(schema_path)
    mapper = Mapper(schema)
    stream = load_csv_dict(input_path)
    stream = mapper.map(stream)
    save(stream, output_path, fieldnames=schema.fieldnames)


@cli.command(
    "index", short_help="create collection indices",
)
def index_cmd():
    indexer = Indexer()
    indexer.index()


@cli.command(
    "harmonise",
    short_help="strip whitespace and null fields, remove blank rows and columns",
)
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
@click.argument("schema_path", type=click.Path(exists=True))
@click.argument("issue_path", type=click.Path(exists=True))
def harmonise_cmd(input_path, output_path, schema_path, issue_path):
    resource_hash = input_path.split('/')[-1]
    schema = Schema(schema_path)
    issues = Issues()
    resource_organisation = ResourceOrganisation().resource_organisation
    organisation = Organisation()
    harmoniser = Harmoniser(
        schema, issues, resource_organisation, organisation.organisation_uri
    )
    stream = load_csv_dict(input_path)
    stream = harmoniser.harmonise(stream)
    save(stream, output_path, fieldnames=schema.current_fieldnames)

    issues_file = IssuesFile(path=os.path.join(issue_path, resource_hash + ".csv"))
    issues_file.write_issues(issues)


@cli.command("transform", short_help="transform")
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
@click.argument("schema_path", type=click.Path(exists=True))
def transform_cmd(input_path, output_path, schema_path):
    schema = Schema(schema_path)
    organisation = Organisation()
    transformer = Transformer(schema, organisation.organisation)
    stream = load_csv_dict(input_path)
    stream = transformer.transform(stream)
    save(stream, output_path, schema.schema["digital-land"]["fields"])
    schema = Schema(schema_path)


@cli.command("pipeline", short_help="convert, normalise, map, harmonise, transform")
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
@click.argument("schema_path", type=click.Path(exists=True))
@click.argument("issue_path", type=click.Path(exists=True))
def pipeline_cmd(input_path, output_path, schema_path, issue_path):
    resource_hash = input_path.split('/')[-1]
    schema = Schema(schema_path)
    organisation = Organisation()
    resource_organisation = ResourceOrganisation().resource_organisation
    issues = Issues()

    normaliser = Normaliser()
    mapper = Mapper(schema)
    harmoniser = Harmoniser(
        schema, issues, resource_organisation, organisation.organisation_uri
    )
    transformer = Transformer(schema, organisation.organisation)

    # pipeline = compose(normaliser.normalise, mapper.map, harmoniser.harmonise, transformer.transform)

    stream = load(input_path)
    normalised = normaliser.normalise(stream)
    normalised_tmp = tempfile.NamedTemporaryFile(
        suffix=f".{resource_hash}.csv"  # Keep the resource hash in the temp filename
    )
    save(normalised, normalised_tmp.name)

    stream_dict = load_csv_dict(normalised_tmp.name)
    mapped = mapper.map(stream_dict)
    harmonised = harmoniser.harmonise(mapped)
    transformed = transformer.transform(harmonised)
    save(transformed, output_path, fieldnames=schema.schema["digital-land"]["fields"])

    issues_file = IssuesFile(path=os.path.join(issue_path, resource_hash + ".csv"))
    issues_file.write_issues(issues)


@cli.command("generate", short_help="generate json schema")
@click.argument("schema_path", type=click.Path(exists=True))
def generate_cmd(schema_path):
    generate.json_schema(schema_path)
