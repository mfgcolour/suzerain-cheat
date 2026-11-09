import ast
import json
import os
import re
from pathlib import Path


# Match entries such as:
# [\"GameCondition.Turn01_EnT_EconomicOverview\"]=false
# Also accepts unescaped quotes, integers, and quoted string values.
ENTRY_PATTERN = re.compile(
    r"""\[\s*\\?["']([^"']+)\\?["']\s*\]\s*=\s*(true|false|-?\d+|'[^']*'|"[^"]*")""",
    re.IGNORECASE,
)

# Special dictionary key used to store an entry's value in the navigation tree.
VALUE_MARKER = "__value__"


def parse_value(text):
    """Convert text such as 'false', '42', or a quoted string to a Python value."""
    text = text.strip()

    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False

    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text


def format_value(value):
    """Convert a Python value to the text format used in the file."""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return repr(value)
    return str(value)


def split_path(path):
    """
    Split a key at dots and qualifying underscores.

    An underscore starts a new path level only when the next part has
    more than 3 characters. Short parts remain attached to the previous part.
    """
    result = []

    for dotted_part in path.split("."):
        pieces = dotted_part.split("_")
        current = pieces[0]

        for piece in pieces[1:]:
            if len(piece) > 3:
                result.append(current)
                current = piece
            else:
                current += "_" + piece

        result.append(current)

    return result


def load_file(file_path):
    """Read the file and build the navigation tree and entry-value mapping."""
    text = file_path.read_text(encoding="utf-8")
    tree = {}
    entries = {}
    matches = list(ENTRY_PATTERN.finditer(text))

    for match in matches:
        key, raw_value = match.groups()
        value = parse_value(raw_value)

        # Strip trailing backslashes from the navigation path, if present.
        # Keep the original key in entries so saving still matches the file.
        navigation_key = key.rstrip("\\")
        node = tree

        for part in split_path(navigation_key):
            node = node.setdefault(part, {})

        node[VALUE_MARKER] = value
        entries[key] = value

    return text, tree, entries, matches


def get_node(tree, path_parts):
    """Return the tree node at the requested path, or raise KeyError."""
    node = tree

    for part in path_parts:
        if part not in node or not isinstance(node[part], dict):
            raise KeyError(f"No such location: {'/'.join(path_parts)}")
        node = node[part]

    return node


def parse_user_value(text):
    """Interpret a CLI value as a boolean, number, or string."""
    text = text.strip()

    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False

    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text


def save_file(file_path, original_text, entries, matches):
    """Replace entry values while preserving all other file content."""
    updated_text = original_text

    # Replace from the end of the file toward the beginning so text positions
    # for earlier matches remain valid.
    for match in reversed(matches):
        key = match.group(1)

        if key not in entries:
            continue

        value_start, value_end = match.span(2)
        replacement = format_value(entries[key])

        updated_text = (
            updated_text[:value_start]
            + replacement
            + updated_text[value_end:]
        )

    file_path.write_text(updated_text, encoding="utf-8")
    return updated_text


def comment_key(path_parts):
    """Convert a tree path into the key used in the comments JSON file."""
    return "/".join(path_parts)


def load_comments(comments_path):
    """Load path-specific comments from JSON, or return an empty mapping."""
    if not comments_path.exists():
        return {}

    try:
        data = json.loads(comments_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {
                str(path): str(comment)
                for path, comment in data.items()
            }
    except (json.JSONDecodeError, OSError) as error:
        print(f"Could not load comments from {comments_path}: {error}")

    return {}


def save_comments(comments_path, comments):
    """Write path-specific comments to JSON."""
    comments_path.write_text(
        json.dumps(comments, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def display_comment(path_parts, comments):
    """Display the comment associated with the current path, if any."""
    key = comment_key(path_parts)
    comment = comments.get(key)

    if comment:
        print(f"# {comment}")


def main():
    """Prompt for the file, then run the navigation and editing CLI."""
    folder = input("Folder containing the file: ").strip()
    filename = input("File name: ").strip()
    file_path = Path(folder).expanduser() / filename

    if not file_path.is_file():
        print(f"File not found: {file_path}")
        return

    # Shared comments file in the directory from which the script was launched.
    comments_path = Path.cwd() / "comments.json"

    original_text, tree, entries, matches = load_file(file_path)
    comments = load_comments(comments_path)

    if not entries:
        print("No matching entries found. The file was not changed.")
        print(r'Expected entries like [\"name\"]=false.')
        return

    print(f"Loaded {len(entries)} entries.")
    print(
        "\nCommands: cd <name|..|/>, clear, # <comment>, help, ls, pwd, set set <path> <value>, save, quit, "
    )


    current_path = []

    while True:
        location = "/" + "/".join(current_path)
        command = input(f"{location}> ").strip()

        if not command:
            continue

        if command == "clear":
            os.system("cls" if os.name == "nt" else "clear")

        elif command == "help":
            print("cd")
            print("Change Directory")
            print("Example:cd BaseGame")
            print("Will move to the BaseGame directory")
            print("cd ..")
            print("Will move you up one directory")
            print("\nclear")
            print("Will clear the console of all prior messages.")
            print("\n#")
            print("A comment is a note you can leave yourself about a given directory")
            print("#This is a test comment")
            print("\nhelp")
            print("Tells you about commands")
            print("\nls")
            print("Shows your current directory, and any values that can be changed.")
            print("Example: BaseGame/ is a directory.")
            print("/BaseGame/Reform/Assembly/Vote is a value.")
            print("\npwd")
            print("Shows your current working directory")
            print("Example:/BaseGame/Reform/Assembly")
            print("\nquit")
            print("closes the application")
            print("\nsave")
            print("Saves yours inputted file")
            print("\nset")
            print("Sets a given value")
            print("Example: /BaseGame/Reform/Assembly> set Vote 116 \nSet Vote = 116")
            print("You can pass direct values in as well, /> set BaseGame.Reform_Assembly_Vote 116\nWill do the same as the previous command")


        elif command == "ls":
            try:
                node = get_node(tree, current_path)
            except KeyError as error:
                print(error)
                continue

            for name in sorted(node):
                child = node[name]

                if name == VALUE_MARKER:
                    print(f"= {child!r}")
                elif VALUE_MARKER in child:
                    print(f"{name} = {child[VALUE_MARKER]!r}")
                else:
                    print(f"{name}/")

        elif command.startswith("cd "):
            target = command[3:].strip()

            if target == "/":
                current_path = []
                display_comment(current_path, comments)
            elif target == "..":
                if current_path:
                    current_path.pop()
                display_comment(current_path, comments)
            else:
                candidate = current_path + split_path(target.rstrip("\\"))

                try:
                    node = get_node(tree, candidate)

                    if VALUE_MARKER in node:
                        print("That entry is a value, not a folder.")
                    else:
                        current_path = candidate
                        display_comment(current_path, comments)
                except KeyError:
                    print(f"No such location: {target}")

        elif command == "pwd":
            print("/" + "/".join(current_path))

        elif command.startswith("#"):
            # Save a comment for the current path immediately.
            # An empty comment removes that path's comment.
            comment = command[1:].strip()
            key = comment_key(current_path)

            if comment:
                comments[key] = comment
                print(f"Comment set for /{key}" if key else "Comment set for /")
            else:
                comments.pop(key, None)
                print(
                    f"Comment removed for /{key}"
                    if key
                    else "Comment removed for /"
                )

            try:
                save_comments(comments_path, comments)
                print(f"Comments saved to {comments_path}")
            except OSError as error:
                print(f"Could not save comments: {error}")

        elif command.startswith("set "):
            remainder = command[4:].strip()
            path, separator, raw_value = remainder.partition(" ")

            if not separator:
                print("Usage: set <path> <value>")
                continue

            target_parts = split_path(path.rstrip("\\"))
            normalized_path = current_path + target_parts

            try:
                node = get_node(tree, normalized_path)
            except KeyError:
                # If the relative path does not exist, try from the root.
                normalized_path = target_parts

                try:
                    node = get_node(tree, normalized_path)
                except KeyError:
                    print(f"No such entry: {path}")
                    continue

            if VALUE_MARKER not in node:
                print(f"That path is a folder, not an entry: {path}")
                continue

            matching_key = None
            for key in entries:
                if split_path(key.rstrip("\\")) == normalized_path:
                    matching_key = key
                    break

            if matching_key is None:
                print(f"Could not match the path to a file entry: {path}")
                continue

            value = parse_user_value(raw_value)
            node[VALUE_MARKER] = value
            entries[matching_key] = value
            print(f"Set {path} = {value!r}")

        elif command == "save":
            try:
                save_file(file_path, original_text, entries, matches)
                save_comments(comments_path, comments)
                print(f"Saved changes to {file_path}")
                print(f"Saved comments to {comments_path}")
            except OSError as error:
                print(f"Could not save: {error}")

        elif command == "quit":
            answer = input("Save changes before quitting? [y/N] ").strip().lower()

            if answer == "y":
                try:
                    save_file(file_path, original_text, entries, matches)
                    save_comments(comments_path, comments)
                    print(f"Saved changes to {file_path}")
                    print(f"Saved comments to {comments_path}")
                except OSError as error:
                    print(f"Could not save: {error}")

            break

        else:
            print(
                "Unknown command. Try: ls, cd, pwd, set, #, "
                "clear, save, quit"
            )


if __name__ == "__main__":
    main()
