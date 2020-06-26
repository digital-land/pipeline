from collections import defaultdict
from .load import load_csv_dict


class ResourceOrganisation:
    resource_organisation_path = "index/resource-organisation.csv"
    resource_organisation = defaultdict(list)

    def __init__(self, resource_organisation_path=None):
        if resource_organisation_path:
            self.resource_organisation_path = resource_organisation_path

        self.load_resource_organisation()

    def load_resource_organisation(self):
        for row in load_csv_dict(self.resource_organisation_path):
            self.resource_organisation[row["resource"]].append(
                {
                    "organisation": row["organisation"],
                    "start-date": row["start-date"],
                    "end-date": row["end-date"],
                }
            )

        # REMOVE BELOW - CHECKING CODE
        for key, value in self.resource_organisation.items():
            if len(value) == 1:
                continue

            start_date = None
            for org in value:
                if not start_date:
                    start_date = org["start-date"]
                    continue

                if org["start-date"] != start_date:
                    __import__('pdb').set_trace()
