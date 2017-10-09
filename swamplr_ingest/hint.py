import logging
import os
import json


class HintFiles():

    """Get hint files for each directory from base_dir to object_dir and allow each sub-dir to overwrite/append."""

    def __init__(self, base_dir, object_dir):
        """Load dirs and load hint files."""
        self.hint_file_name = "hint.json"
        self.base_dir = os.path.realpath(os.path.normpath(base_dir)).rstrip("/")
        self.object_dir = os.path.realpath(os.path.normpath(object_dir)).rstrip("/")
        self.hint_data = {}

        # Make sure object_dir is a subdirectory of base_dir.
        if self.object_dir.startswith(self.base_dir):
            self._load_hint_data()
        else:
            logging.warning("Object path {0} not found in base path {1}.".format(self.object_dir, self.base_dir))

    def _load_hint_data(self):
        """Load each hint file successively."""

        object_dir_parts = self.object_dir[len(self.base_dir):].split("/")
        object_dirs = [""] + [part for part in object_dir_parts if part != ""]

        current_dir = self.base_dir

        for part in object_dirs:
            current_dir = os.path.join(current_dir, part)
            self._load_hint_file(current_dir)

    def _load_hint_file(self, path):
        """Check for hint file in current directory."""

        hint_path = os.path.join(path, self.hint_file_name)

        if os.path.isfile(hint_path):
            data = self._open_file(hint_path)
            self.hint_data.update(data)

    def _open_file(self, path):
        """Read json file."""
        with open(path) as f:
            data = json.load(f)
        return data

    def get_hint_data(self):
        """Return data."""
        return self.hint_data
