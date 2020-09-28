import csv
import json
import xml.etree.ElementTree
import logging
import subprocess
from io import StringIO

import pandas as pd

from .load import (
    detect_encoding,
    load,
    load_csv,
    load_csv_dict,
    reader_with_line,
    resource_hash_from,
)


class Converter:
    def __init__(self, conversions={}):
        self.conversions = conversions

    def convert(self, path):
        encoding = detect_encoding(path)
        logging.debug("encoding detected: %s", encoding)
        if encoding:
            return self._convert_text_file(path, encoding)
        else:
            return self._convert_binary_file(path)

    def _convert_text_file(self, path, encoding):
        f = open(path, encoding=encoding, newline="")
        content = f.read(10)
        f.seek(0)

        if content.lower().startswith("<!doctype "):
            logging.debug(f"{path} has <!doctype")
            return None
        elif content.lower().startswith("<?xml "):
            logging.debug(f"{path} has <?xml")
            return self._convert_xml_file(path)
        elif content.lower().startswith("<wfs:"):
            logging.debug(f"{path} has <?xml")
            return self._convert_xml_file(path)
        elif content.lower().startswith("{"):
            logging.debug(f"{path} has {{")
            return self._convert_json_file(f)

        return reader_with_line(f, resource_hash_from(path))

    def _convert_xml_file(self, path):
        tree = xml.etree.ElementTree.parse(path)
        root = tree.getroot()
        logging.debug("root.tag: %s", root.tag)
        __import__('pdb').set_trace()
        if root.tag.startswith("{http://www.opengis.net/wfs"):
            self._convert_wfs_file(path)

    def _convert_wfs_file(self, path):
        logging.debug("Converting wfs file")
        execute(["ogr2ogr", "-oo", "DOWNLOAD_SCHEMA=NO", "-lco", "GEOMETRY=AS_WKT", "-lco", "LINEFORMAT=CRLF", "-f", "CSV", "/tmp/wfs_converted_output", path])
        logging.debug("Conversion complete")

    def _convert_json_file(self, f):
        logging.debug("JSON detected")
        json.load(f)
        return []
        raise ValueError("json reader not implemented")

    def _convert_binary_file(self, path):
        excel_reader = self._excel_reader(path)
        if excel_reader:
            return excel_reader

    def _excel_reader(self, path):
        try:
            excel = pd.read_excel(path)
        except:  # noqa: E722
            return None

        string = excel.to_csv(
            index=None, header=True, encoding="utf-8", quoting=csv.QUOTE_ALL
        )
        f = StringIO(string)

        return reader_with_line(f, resource_hash_from(path))

    def _xml_reader(self, path):
        raise ValueError("xml reader not implemented")


def execute(command):
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        outs, errs = proc.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        outs, errs = proc.communicate()

    return proc.returncode, outs.decode("utf-8"), errs.decode("utf-8")
