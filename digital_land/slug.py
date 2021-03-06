import re


class Slugger:
    def __init__(self, prefix, key_field, scope_field=None):
        self.prefix = prefix
        self.key_field = key_field
        self.scope_field = scope_field

    def _generate_slug(self, row):
        return self.generate_slug(self.prefix, self.key_field, row, self.scope_field)

    bad_chars = re.compile(r"[^A-Za-z0-9]")

    @staticmethod
    def generate_slug(prefix, key_field, row, scope_field=None):
        """
        Helper method to provide slug without a Slugger instance
        """
        for field in [scope_field, key_field]:
            if not field:
                continue
            if field not in row or not row[field]:
                return None

        scope = None
        if scope_field:
            scope = row[scope_field].replace(":", "/")
            key = Slugger.bad_chars.sub("-", row[key_field])
        else:
            key_parts = row[key_field].split(":")
            if len(key_parts) != 2:
                raise ValueError("expected curie, found %s", row[key_field])
            key_parts[1] = Slugger.bad_chars.sub("-", key_parts[1])
            key = "/".join(key_parts)

        return "/" + "/".join(filter(None, [prefix, scope, key]))

    def slug(self, reader):
        for stream_data in reader:
            row = stream_data["row"]
            row["slug"] = self._generate_slug(row)
            yield stream_data
