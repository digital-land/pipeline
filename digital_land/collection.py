import os
import re
import logging

from pathlib import Path
from datetime import datetime

from .register import hash_value
from .schema import Schema
from .store.csv import CSVStore
from .store.item import ItemStore
from .makerules import pipeline_makerules

collection_directory = "./collection"


def isodate(s):
    return datetime.fromisoformat(s).strftime("%Y-%m-%d")


def resource_path(resource, directory=collection_directory):
    return Path(directory) / "resource" / resource


def resource_url(collection, resource):
    return (
        "https://raw.githubusercontent.com/digital-land/"
        + "%s-collection/master/collection/resource/%s" % (collection, resource)
    )


# a store of log files created by the collector
# collecton/log/YYYY-MM-DD/{endpoint#}.json
class LogStore(ItemStore):
    def load_item(self, path):
        item = super().load_item(path)
        item = item.copy()

        # migrate content-type and bytes fields
        h = item.get("response-headers", {})
        if "content-type" not in item:
            item["content-type"] = h.get("Content-Type", "")
        if "bytes" not in item:
            item["bytes"] = h.get("Content-Length", "")

        # migrate datetime to entry-date field
        if "datetime" in item:
            if "entry-date" not in item:
                item["entry-date"] = item["datetime"]
            del item["datetime"]

        # migrate url to endpoint-url field
        if "url" in item:
            if "endpoint-url" not in item:
                item["endpoint-url"] = item["url"]
            del item["url"]

        # default the endpoint value
        if "endpoint" not in item:
            item["endpoint"] = hash_value(item["endpoint-url"])
        self.check_item_path(item, path)

        return item

    def save_item(self, item, path):
        del item["endpoint"]
        return super().save_item(item)

    def check_item_path(self, item, path):
        m = re.match(r"^.*\/([-\d]+)\/(\w+).json", path)
        (date, endpoint) = m.groups()

        if not item.get("entry-date", "").startswith(date):
            logging.warning(
                "incorrect date in path %s for entry-date %s"
                % (path, item["entry-date"])
            )

        # print(item["url"], hash_value(item["url"]))
        if endpoint != item["endpoint"]:
            logging.warning(
                "incorrect endpoint in path %s expected %s" % (path, item["endpoint"])
            )


# a register of resources constructed from the log register
class ResourceLogStore(CSVStore):
    def load(self, log, source, directory=collection_directory):
        resources = {}
        today = datetime.utcnow().isoformat()[:10]

        for entry in log.entries:
            if "resource" in entry:
                resource = entry["resource"]
                if resource not in resources:
                    path = resource_path(resource, directory=directory)
                    try:
                        size = os.path.getsize(path)
                    except (FileNotFoundError):
                        logging.warning("missing %s" % (path))
                        size = ""

                    resources[resource] = {
                        "bytes": size,
                        "endpoints": {},
                        "start-date": entry["entry-date"],
                        "end-date": entry["entry-date"],
                    }
                else:
                    resources[resource]["start-date"] = min(
                        resources[resource]["start-date"], entry["entry-date"]
                    )
                    resources[resource]["end-date"] = max(
                        resources[resource]["end-date"], entry["entry-date"]
                    )
                resources[resource]["endpoints"][entry["endpoint"]] = True

        for key, resource in sorted(resources.items()):
            organisations = {}
            for endpoint in resource["endpoints"]:
                for entry in source.records[endpoint]:
                    organisations[entry["organisation"]] = True

            end_date = isodate(resource["end-date"])
            if end_date >= today:
                end_date = ""

            self.add_entry(
                {
                    "resource": key,
                    "bytes": resource["bytes"],
                    "endpoints": ";".join(sorted(resource["endpoints"])),
                    "organisations": ";".join(sorted(organisations)),
                    "start-date": isodate(resource["start-date"]),
                    "end-date": end_date,
                }
            )


# expected this will be based on a Datapackage class
class Collection:
    def __init__(self, name=None, directory=collection_directory):
        self.name = name
        self.directory = directory

    def load_log_items(self, directory=None, log_directory=None):
        if not log_directory:
            directory = directory or self.directory
            log_directory = Path(directory) / "log/*/"

        self.log = LogStore(Schema("log"))
        self.log.load(directory=log_directory)

        self.resource = ResourceLogStore(Schema("resource"))
        self.resource.load(log=self.log, source=self.source)

    def save_csv(self, directory=None):
        if not directory:
            directory = self.directory

        self.endpoint.save_csv(directory=directory)
        self.source.save_csv(directory=directory)
        self.log.save_csv(directory=directory)
        self.resource.save_csv(directory=directory)

    def load(self, directory=None):
        directory = directory or self.directory

        self.source = CSVStore(Schema("source"))
        self.source.load(directory=directory)

        self.endpoint = CSVStore(Schema("endpoint"))
        self.endpoint.load(directory=directory)

        try:
            self.log = CSVStore(Schema("log"))
            self.log.load(directory=directory)

            self.resource = CSVStore(Schema("resource"))
            self.resource.load(directory=directory)
        except (FileNotFoundError):
            self.load_log_items()

    def resource_endpoints(self, resource):
        "return the list of endpoints a resource was collected from"
        return self.resource.records[resource][-1]["endpoints"].split(";")

    def resource_organisations(self, resource):
        "return the list of organisations for which a resource was collected"
        return self.resource.records[resource][-1]["organisations"].split(";")

    def resource_path(self, resource):
        return resource_path(resource, self.directory)

    def pipeline_makerules(self):
        pipeline_makerules(self)
