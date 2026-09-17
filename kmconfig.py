"""Project config + members registry for kubmonitor usage accounting.

A *project config* (yaml) describes one monitored namespace: where its
usage DB lives, which members file maps accounts to people, and how
workloads are labelled (see docs/LABELS.md). A *members file* (yaml) maps
cluster accounts to persons so one person with several accounts becomes a
single row in reports.
"""

import os

import yaml


class ConfigError(Exception):
    pass


class Person:
    def __init__(self, name, email="", accounts=None, status="active",
                 aliases=None):
        self.name = name
        self.email = email
        self.accounts = list(accounts or [])
        self.status = status
        self.aliases = list(aliases or [])


class Members:
    """Account -> person lookup built from members.yaml."""

    def __init__(self, people):
        self.people = people
        self.by_account = {}
        for person in people:
            for account in person.accounts:
                self.by_account[account] = person

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        entries = data.get("members", [])
        people = []
        for entry in entries:
            if not entry.get("name") or not entry.get("accounts"):
                raise ConfigError(
                    f"members file {path}: every entry needs "
                    f"'name' and 'accounts' (bad entry: {entry!r})")
            people.append(Person(
                name=entry["name"],
                email=entry.get("email", ""),
                accounts=[str(a) for a in entry["accounts"]],
                status=entry.get("status", "active"),
                aliases=[str(a) for a in entry.get("aliases", [])],
            ))
        return cls(people)

    @classmethod
    def empty(cls):
        return cls([])

    def person_for(self, account):
        return self.by_account.get(account)

    def display_name(self, account):
        person = self.by_account.get(account)
        return person.name if person else account

    def known_accounts(self):
        return set(self.by_account.keys())

    def name_match_map(self):
        """token -> canonical account, for name-based attribution.

        Includes every account plus every alias (nicknames people embed
        in job names when they don't use the labelled templates); alias
        hits resolve to the person's first account so reports aggregate
        correctly.
        """
        mapping = {account: account for account in self.by_account}
        for person in self.people:
            if not person.accounts:
                continue
            for alias in person.aliases:
                mapping.setdefault(alias, person.accounts[0])
        return mapping


class ProjectConfig:
    def __init__(self, project, namespace, db, members_file="",
                 kube_context="", sample_gpu_util=False,
                 label_prefix="", research_projects=(), path=""):
        self.project = project
        self.namespace = namespace
        self.db = db
        self.members_file = members_file
        self.kube_context = kube_context
        self.sample_gpu_util = sample_gpu_util
        self.label_prefix = label_prefix
        # Known `project` label values. Advisory only: an unlisted value is
        # warned about, never rejected — someone starting a new project must
        # not have to land a config change first.
        self.research_projects = list(research_projects)
        self.path = path

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for required in ("project", "namespace", "db"):
            if not data.get(required):
                raise ConfigError(
                    f"project config {path}: missing required key "
                    f"'{required}'")
        base = os.path.dirname(os.path.abspath(path))

        def resolve(p):
            if not p:
                return p
            p = os.path.expanduser(str(p))
            return p if os.path.isabs(p) else os.path.join(base, p)

        return cls(
            project=str(data["project"]),
            namespace=str(data["namespace"]),
            db=resolve(data["db"]),
            members_file=resolve(data.get("members_file", "")),
            kube_context=str(data.get("kube_context", "") or ""),
            sample_gpu_util=bool(data.get("sample_gpu_util", False)),
            label_prefix=str(data.get("label_prefix", "") or ""),
            research_projects=[
                str(p) for p in (data.get("research_projects") or [])],
            path=os.path.abspath(path),
        )

    def load_members(self):
        if not self.members_file:
            return Members.empty()
        if not os.path.exists(self.members_file):
            raise ConfigError(
                f"members file not found: {self.members_file} "
                f"(referenced by {self.path})")
        return Members.load(self.members_file)

    def kubectl(self, args):
        """Build a kubectl command string honoring kube_context."""
        ctx = f"--context {self.kube_context} " if self.kube_context else ""
        return f"kubectl {ctx}{args}"


def find_default_config():
    """Locate a project config when --config is not given.

    Checked in order: $KUBMONITOR_CONFIG, ~/.config/kubmonitor/project.yaml,
    then the single *.yaml in ~/.config/kubmonitor/ if exactly one exists.
    """
    env = os.environ.get("KUBMONITOR_CONFIG")
    if env and os.path.exists(env):
        return env
    cfg_dir = os.path.expanduser("~/.config/kubmonitor")
    default = os.path.join(cfg_dir, "project.yaml")
    if os.path.exists(default):
        return default
    if os.path.isdir(cfg_dir):
        candidates = [os.path.join(cfg_dir, f) for f in os.listdir(cfg_dir)
                      if f.endswith((".yaml", ".yml"))]
        if len(candidates) == 1:
            return candidates[0]
    return None
