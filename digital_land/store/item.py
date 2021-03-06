# a store of individual item.json files

import os
import glob
import logging
from pathlib import Path

from ..register import Item
from .csv import CSVStore


class ItemStore(CSVStore):
    def item_path(self, item, directory=""):
        return Path(directory) / (item.hash + ".json")

    def save_item(self, item, path):
        data = item.pack()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            logging.info("saving %s" % (path))
            with open(path, "wb") as f:
                f.write(data)

    def save_items(self, path):
        raise NotImplementedError

    def save(self, *args, **kwargs):
        self.save_items(*args, **kwargs)

    def load_item(self, path):
        data = open(path).read()
        item = Item()
        item.unpack(data)
        return item

    def load_items(self, directory="."):
        path = "%s/*.json" % (directory)
        logging.debug("loading %s" % (path))
        for path in sorted(glob.glob(path)):
            item = self.load_item(path)
            self.add_entry(item)

    def load(self, *args, **kwargs):
        self.load_items(*args, **kwargs)
