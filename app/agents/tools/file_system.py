import os

from agno.tools import Toolkit


class FileSystemTools(Toolkit):
    """Tools for reading, writing, and editing files."""

    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir or os.getcwd()
        super().__init__(
            name="file_system",
            tools=[self.read_file, self.write_file, self.edit_file],
        )

    def _resolve(self, path: str) -> str:
        """Resolve a user-provided path safely within the base directory.

        Uses ``os.path.realpath`` so that any symlinks in the path are
        resolved before we validate that the final target is still under
        ``self.base_dir``. This prevents bypasses where a symlink inside the
        base directory points outside of it.
        """
        base_real = os.path.realpath(self.base_dir)
        resolved = os.path.realpath(os.path.join(self.base_dir, path))

        # Ensure the resolved path is within the (canonical) base directory
        common = os.path.commonpath([base_real, resolved])
        if common != base_real:
            raise ValueError(f"Path {path} is outside the base directory")
        return resolved

    def read_file(self, path: str) -> str:
        """Read the contents of a file.

        Args:
            path(str): The relative path to the file to read.

        Returns:
            str: The contents of the file.
        """
        resolved = self._resolve(path)
        with open(resolved) as f:
            return f.read()

    def write_file(self, path: str, content: str) -> str:
        """Write content to a file. Creates the file and parent directories if they don't exist.

        Args:
            path(str): The relative path to the file to write.
            content(str): The content to write to the file.

        Returns:
            str: Confirmation message.
        """
        resolved = self._resolve(path)
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        with open(resolved, "w") as f:
            f.write(content)
        return f"Written to {path}"

    def edit_file(self, path: str, old_string: str, new_string: str) -> str:
        """Edit a file by replacing a string.

        Args:
            path(str): The relative path to the file to edit.
            old_string(str): The exact string to find and replace.
            new_string(str): The string to replace it with.

        Returns:
            str: Confirmation message.
        """
        resolved = self._resolve(path)
        with open(resolved) as f:
            content = f.read()
        if old_string not in content:
            return f"Error: '{old_string}' not found in {path}"
        content = content.replace(old_string, new_string, 1)
        with open(resolved, "w") as f:
            f.write(content)
        return f"Edited {path}"