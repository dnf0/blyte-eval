"""Builds the image the agent actually runs inside.

The agent must not run on the host. A host process can read the task's tests/
directory and reach the Docker daemon, and no CLI flag reliably prevents either.
Running the agent inside a container removes the question: there is nothing to
restrict because the host is simply not reachable.

The image is the task image plus an agent CLI layer, so the agent has the task's
own toolchain natively -- no bridge script, no docker socket, no MCP shim. The
task's own filesystem is untouched: the CLI is installed under /opt/agent.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from lab.sandbox.docker_manager import DockerManager

logger = logging.getLogger("superstate_eval.agent_image")

# Installed outside /app so it can never appear in the graded diff.
AGENT_PREFIX = "/opt/agent"

# The agent runs as a non-root user: the CLI refuses to bypass permission
# prompts as root, and an unattended agent should not be root in any case.
AGENT_USER = "agent"
AGENT_UID = 1000
AGENT_HOME = "/home/agent"

CLAUDE_CODE_DOCKERFILE = """FROM {base}
USER root
ENV NPM_CONFIG_PREFIX={prefix}
ENV PATH={prefix}/bin:$PATH
RUN npm install -g --no-fund --no-audit @anthropic-ai/claude-code@{version} \
    && {prefix}/bin/claude --version
RUN (getent passwd {uid} >/dev/null && usermod -l {user} -d {home} -m "$(getent passwd {uid} \
        | cut -d: -f1)" || useradd -m -u {uid} -s /bin/bash {user}) \
    && mkdir -p {home} && chown -R {uid}:{uid} {home}
ENV HOME={home}
WORKDIR /app
"""


def _slug(text: str) -> str:
    """Docker tags allow a restricted character set; image refs do not."""
    cleaned = re.sub(r"[^a-z0-9_.-]+", "-", text.lower()).strip("-._")
    return cleaned[:80] or "task"


class AgentImageBuilder:
    """Builds and caches per-task agent images."""

    def __init__(self, docker_manager: "DockerManager", build_timeout_sec: int = 1800) -> None:
        self.docker_manager = docker_manager
        self.build_timeout_sec = build_timeout_sec

    def image_tag(self, base_image: str, cli: str, version: str) -> str:
        """A deterministic tag: this image holds no secrets, so caching is safe.

        Unlike the verifier image, which contains the held-out tests and must not
        outlive a run, the agent image is just the task environment plus a public
        CLI. Caching it avoids re-installing on every task.
        """
        digest = hashlib.sha256(base_image.encode("utf-8")).hexdigest()[:12]
        return f"superstate-eval-agent/{_slug(cli)}-{_slug(version)}-{digest}:latest"

    def build_claude_code(self, base_image: str, version: str = "latest") -> str:
        """Build (or reuse) an image with the Claude Code CLI on top of `base_image`."""
        tag = self.image_tag(base_image, "claude-code", version)

        if self._image_exists(tag):
            logger.info("Reusing cached agent image %s", tag)
            return tag

        dockerfile = CLAUDE_CODE_DOCKERFILE.format(
            base=base_image,
            prefix=AGENT_PREFIX,
            version=version,
            user=AGENT_USER,
            uid=AGENT_UID,
            home=AGENT_HOME,
        )
        logger.info("Building agent image %s from %s", tag, base_image)
        self.docker_manager.build_image_from_dockerfile(
            dockerfile=dockerfile, tag=tag, timeout=self.build_timeout_sec
        )
        return tag

    def _image_exists(self, tag: str) -> bool:
        try:
            self.docker_manager.client.images.get(tag)
            return True
        except Exception:
            return False
