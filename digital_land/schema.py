from collections import OrderedDict

# TBD: make part of the specification module and use data from:
# https://digital-land.github.io/specification/
schemas = {
    "log": {
        "fields": [
            "bytes",
            "content-type",
            "elapsed",
            "endpoint",
            "resource",
            "status",
            "entry-date",
            "start-date",
            "end-date",
        ],
        "key": "endpoint",
    },
    "endpoint": {
        "fields": [
            "endpoint",
            "endpoint-url",
            "parameters",
            "plugin",
            "entry-date",
            "start-date",
            "end-date",
        ],
        "key": "endpoint",
    },
    "source": {
        "fields": [
            "attribution",
            "collection",
            "documentation-url",
            "endpoint",
            "licence",
            "organisation",
            "pipelines",
            "entry-date",
            "start-date",
            "end-date",
        ],
        "key": "endpoint",
    },
    "resource": {
        "fields": [
            "resource",
            "bytes",
            "organisations",
            "endpoints",
            "start-date",
            "end-date",
        ],
        "key": "resource",
    },
}


class Field:
    "information about a field"

    def __init__(self, name):
        self.name = name


class Schema:
    # TBD: make a singleton for each name
    def __init__(self, name):
        self.name = name
        self.key = schemas[name]["key"]
        self.field = OrderedDict()
        for field in schemas[name]["fields"]:
            self.field[field] = Field(field)
        self.fieldnames = self.field.keys()
