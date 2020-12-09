import functools
import logging
import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import canonicaljson
import click
from digital_land_frontend.render import Renderer

from .collect import Collector
from .collection import Collection, resource_path
from .convert import Converter
from .harmonise import Harmoniser
from .index import Indexer
from .issues import Issues, IssuesFile
from .load import LineConverter, load_csv, load_csv_dict
from .map import Mapper
from .normalise import Normaliser
from .organisation import Organisation
from .pipeline import Pipeline
from .plugin import get_plugin_manager
from .save import save
from .schema import Schema
from .specification import Specification
from .transform import Transformer
from .update import add_new_source_endpoint, get_failing_endpoints_from_registers

PIPELINE = None
SPECIFICATION = None


# Custom decorators for common command arguments
def input_output_path(f):
    arguments = [
        click.argument("input-path", type=click.Path(exists=True)),
        click.argument("output-path", type=click.Path(), default=""),
    ]
    return functools.reduce(lambda x, arg: arg(x), reversed(arguments), f)


def pipeline_name(f):
    return click.option("--pipeline-name", "-n", type=click.STRING)(f)


def pipeline_dir(f):
    return click.option("--pipeline-dir", "-p", type=click.Path(), default="pipeline/")(
        f
    )


def collection_dir(f):
    return click.option(
        "--collection-dir",
        "-c",
        type=click.Path(exists=True),
        default="collection/",
    )(f)


def specification_dir(f):
    return click.option(
        "--specification-dir",
        "-s",
        type=click.Path(exists=True),
        default="specification/",
    )(f)


def issue_dir(f):
    return click.option(
        "--issue-dir", "-i", type=click.Path(exists=True), default="issue/"
    )(f)


def endpoint_path(f):
    return click.option(
        "--endpoint-path",
        type=click.Path(exists=True),
        default="collection/endpoint.csv",
    )(f)


def source_path(f):
    return click.option(
        "--source-path",
        type=click.Path(exists=True),
        default="collection/source.csv",
    )(f)


@click.group()
@click.option("-d", "--debug/--no-debug", default=False)
@pipeline_name
@pipeline_dir
@specification_dir
def cli(debug, pipeline_name, pipeline_dir, specification_dir):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")
    global PIPELINE
    global SPECIFICATION
    PIPELINE = Pipeline(pipeline_dir, pipeline_name)
    SPECIFICATION = Specification(specification_dir)


@cli.command("fetch")
@click.argument("url")
def fetch_cmd(url):
    """fetch a single source endpoint URL, and add it to the collection"""
    collector = Collector(PIPELINE.name)
    collector.fetch(url)


@cli.command("collect")
@click.argument(
    "endpoint-path",
    type=click.Path(exists=True),
    default="collection/endpoint.csv",
)
def collect_cmd(endpoint_path):
    """fetch the sources listed in the endpoint-url column of the ENDPOINT_PATH CSV file"""
    collector = Collector(PIPELINE.name)
    collector.collect(endpoint_path)


#
#  collection commands
#  TBD: make sub commands
#
@cli.command(
    "index",
    short_help="create collection indices",
)
def index_cmd():
    # TBD: replace with Collection()
    indexer = Indexer()
    indexer.index()


@cli.command("collection-list-resources", short_help="list resources for a pipeline")
@collection_dir
def pipeline_collection_list_resources_cmd(collection_dir):
    collection = Collection(collection_dir)
    collection.load()
    for resource in sorted(collection.resource.records):
        print(resource_path(resource, directory=collection_dir))


@cli.command("collection-save-csv", short_help="save collection as CSV package")
@collection_dir
def pipeline_collection_save_csv_cmd(collection_dir):
    try:
        os.remove(Path(collection_dir) / "log.csv")
        os.remove(Path(collection_dir) / "resource.csv")
    except OSError:
        pass
    collection = Collection(collection_dir)
    collection.load()
    collection.save_csv()


#
#  pipeline commands
#
@cli.command("convert", short_help="convert to a well-formed, UTF-8 encoded CSV file")
@input_output_path
def convert_cmd(input_path, output_path):
    if not output_path:
        output_path = default_output_path_for("converted", input_path)

    converter = Converter(PIPELINE.conversions())
    reader = converter.convert(input_path)
    if not reader:
        logging.error(f"Unable to convert {input_path}")
        sys.exit(2)
    save(reader, output_path)


@cli.command("normalise", short_help="removed padding, drop empty rows")
@input_output_path
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
    if not output_path:
        output_path = default_output_path_for("normalised", input_path)

    resource_hash = resource_hash_from(input_path)
    stream = load_csv(input_path)
    normaliser = Normaliser(PIPELINE.skip_patterns(resource_hash), null_path=null_path)
    stream = normaliser.normalise(stream)
    save(stream, output_path)


@cli.command("map", short_help="map misspelt column names to those in a pipeline")
@input_output_path
def map_cmd(input_path, output_path):
    if not output_path:
        output_path = default_output_path_for("mapped", input_path)

    resource_hash = resource_hash_from(input_path)
    fieldnames = intermediary_fieldnames(SPECIFICATION, PIPELINE)
    mapper = Mapper(
        fieldnames,
        PIPELINE.columns(resource_hash),
        PIPELINE.concatenations(resource_hash),
    )
    stream = load_csv_dict(input_path)
    stream = mapper.map(stream)
    save(stream, output_path, fieldnames=fieldnames)


@cli.command(
    "harmonise",
    short_help="strip whitespace and null fields, remove blank rows and columns",
)
@input_output_path
@issue_dir
def harmonise_cmd(input_path, output_path, issue_dir):
    if not output_path:
        output_path = default_output_path_for("harmonised", input_path)

    resource_hash = resource_hash_from(input_path)
    issues = Issues()

    collection = Collection()
    collection.load()

    organisation_uri = Organisation().organisation_uri
    patch = PIPELINE.patches(resource_hash)
    fieldnames = intermediary_fieldnames(SPECIFICATION, PIPELINE)

    pm = get_plugin_manager()

    harmoniser = Harmoniser(
        SPECIFICATION,
        PIPELINE,
        issues,
        collection,
        organisation_uri,
        patch,
        pm,
    )

    stream = load_csv_dict(input_path)
    stream = harmoniser.harmonise(stream)
    save(stream, output_path, fieldnames=fieldnames)

    issues_file = IssuesFile(path=os.path.join(issue_dir, resource_hash + ".csv"))
    issues_file.write_issues(issues)


@cli.command("transform", short_help="transform")
@input_output_path
def transform_cmd(input_path, output_path):
    if not output_path:
        output_path = default_output_path_for("transformed", input_path)

    organisation = Organisation()
    transformer = Transformer(
        SPECIFICATION.schema_field[PIPELINE.schema],
        PIPELINE.transformations(),
        organisation.organisation,
    )
    stream = load_csv_dict(input_path)
    stream = transformer.transform(stream)
    save(stream, output_path, SPECIFICATION.current_fieldnames(PIPELINE.schema))


@cli.command("pipeline", short_help="convert, normalise, map, harmonise, transform")
@input_output_path
@click.option(
    "--null-path",
    type=click.Path(exists=True),
    help="patterns for null fields",
    default=None,
)
@issue_dir
def pipeline_cmd(input_path, output_path, null_path, issue_dir):
    resource_hash = resource_hash_from(input_path)
    organisation = Organisation()
    issues = Issues()

    fieldnames = intermediary_fieldnames(SPECIFICATION, PIPELINE)
    patch = PIPELINE.patches(resource_hash)

    collection = Collection()
    collection.load()
    line_converter = LineConverter()
    pm = get_plugin_manager()

    converter = Converter(PIPELINE.conversions())

    normaliser = Normaliser(PIPELINE.skip_patterns(resource_hash), null_path=null_path)
    mapper = Mapper(
        fieldnames,
        PIPELINE.columns(resource_hash),
        PIPELINE.concatenations(resource_hash),
    )
    harmoniser = Harmoniser(
        SPECIFICATION,
        PIPELINE,
        issues,
        collection,
        Organisation().organisation_uri,
        patch,
        pm,
    )
    transformer = Transformer(
        SPECIFICATION.schema_field[PIPELINE.schema],
        PIPELINE.transformations(),
        organisation.organisation,
    )

    pipeline = compose(
        converter.convert,
        normaliser.normalise,
        line_converter.convert,
        mapper.map,
        harmoniser.harmonise,
        transformer.transform,
    )

    output = pipeline(input_path)

    save(
        output,
        output_path,
        fieldnames=SPECIFICATION.current_fieldnames(PIPELINE.schema),
    )

    issues_file = IssuesFile(path=os.path.join(issue_dir, resource_hash + ".csv"))
    issues_file.write_issues(issues)


# Endpoint commands


@cli.command("endpoints-check", short_help="check logs for failing endpoints")
@click.argument("first-date", type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option(
    "--log-dir",
    type=click.Path(exists=True),
    help="path to log files",
    default="collection/log/",
)
@endpoint_path
@click.option(
    "--last-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="upper bound of date range to consider",
    default=str(date.today()),
)
def endpoints_check_cmd(first_date, log_dir, endpoint_path, last_date):
    """find active endpoints that are failing during collection"""
    output = get_failing_endpoints_from_registers(
        log_dir, endpoint_path, first_date.date(), last_date.date()
    )
    print(canonicaljson.encode_canonical_json(output))


@cli.command(
    "add-source-endpoint",
    short_help="Add a new source/endpoint entry",
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True),
)
@click.pass_context
@click.argument("endpoint-url", type=click.STRING)
@click.argument("organisation", type=click.STRING)
@collection_dir
def add_source_endpoint_cmd(ctx, endpoint_url, organisation, collection_dir):
    """Add a new source/endpoint entry. Optional parameters are: source, attribution, collection, documentation-url,
    licence, organisation, pipeline, status, plugin, parameters, start-date, end-date"""
    entry = defaultdict(
        str,
        {ctx.args[i].strip("-"): ctx.args[i + 1] for i in range(0, len(ctx.args), 2)},
    )
    allowed_options = set(
        list(Schema("endpoint").fieldnames) + list(Schema("source").fieldnames)
    )
    for key in entry.keys():
        if key not in allowed_options:
            logging.error(f"Optional parameter {key} not recognised")
            sys.exit(2)
    entry["endpoint-url"] = endpoint_url
    entry["organisation"] = organisation
    add_new_source_endpoint(entry, collection_dir)


@cli.command("render")
@click.option("--dataset-path", required=True, type=click.Path())
@click.option("--local", is_flag=True)
def render_cmd(local, dataset_path):
    url_root = None
    if local:
        url_root = "/"
    renderer = Renderer(PIPELINE.name, dataset_path, url_root)
    renderer.render_pages()


def resource_hash_from(path):
    return Path(path).stem


def intermediary_fieldnames(specification, pipeline):
    fieldnames = specification.schema_field[pipeline.schema].copy()
    replacement_fields = list(pipeline.transformations().keys())
    for field in replacement_fields:
        if field in fieldnames:
            fieldnames.remove(field)
    return fieldnames


def default_output_path_for(command, input_path):
    return f"var/{command}/{resource_hash_from(input_path)}.csv"


def compose(*functions):
    def compose2(f, g):
        return lambda x: g(f(x))

    return functools.reduce(compose2, functions, lambda x: x)
