"""The Pulumi program: the maghz docker stack as desired-state resources.

Reads `MaghzSettings` and declares the custom PG image build, the `db`, `ollama`, and
`n8n` containers, their network, and volumes. `define` is the inline program the Automation
API in `runner` converges; it closes over the settings rather than reading Pulumi config.
"""

import pulumi
import pulumi_docker as docker
import pulumi_docker_build as docker_build

from admin.settings import MaghzSettings


# --- [OPERATIONS] ----------------------------------------------------------------------


def define(cfg: MaghzSettings) -> None:  # noqa: PLR0914 - composition root: every local is a named desired-state resource handle
    """Declare every stack resource; bound with the settings and run by the Automation API."""
    infra = cfg.infra

    provider = docker.Provider("colima", host=infra.docker_host)
    on = pulumi.ResourceOptions(provider=provider)
    # The BuildKit build resource is a distinct provider plugin from `docker.Provider`; pin its build
    # daemon to the same Colima socket explicitly rather than letting it fall back to ambient DOCKER_HOST,
    # so the image builds on the same host the runtime resources run on (one host fact, not two sources).
    build = docker_build.Provider("colima-build", host=infra.docker_host)
    on_build = pulumi.ResourceOptions(provider=build)

    image = docker_build.Image(
        "maghz-pg",
        tags=[infra.image_tag],
        context=docker_build.BuildContextArgs(location=str(infra.image_context)),
        dockerfile=docker_build.DockerfileArgs(location=str(infra.image_context / "Dockerfile")),
        build_args={"PARADEDB_TAG": infra.paradedb_tag},
        platforms=[docker_build.Platform.LINUX_ARM64],
        load=True,
        push=False,
        opts=on_build,
    )

    network = docker.Network("maghz", name="maghz", opts=on)
    pg_data = docker.Volume("maghz-data", name="maghz-data", opts=on)
    ollama_models = docker.Volume("ollama-models", name="ollama-models", opts=on)
    n8n_data = docker.Volume("n8n-data", name="n8n-data", opts=on)

    docker.Container(
        "ollama",
        name="maghz-ollama",
        image=infra.ollama_image,
        restart="unless-stopped",
        ports=[docker.ContainerPortArgs(internal=11434, external=infra.ollama_port, ip="127.0.0.1")],
        volumes=[docker.ContainerVolumeArgs(volume_name=ollama_models.name, container_path="/root/.ollama")],
        networks_advanced=[docker.ContainerNetworksAdvancedArgs(name=network.name, aliases=["ollama"])],
        healthcheck=docker.ContainerHealthcheckArgs(tests=["CMD", "ollama", "list"], interval="10s", timeout="5s", retries=5, start_period="20s"),
        opts=on,
    )

    db_container = docker.Container(
        "db",
        name="maghz-db",
        image=image.ref,
        restart="unless-stopped",
        envs=["POSTGRES_USER=maghz", "POSTGRES_DB=maghz", "POSTGRES_HOST_AUTH_METHOD=trust"],
        command=[
            "postgres",
            "-c",
            "shared_preload_libraries=pg_search,pg_cron,pg_net,pg_stat_statements,auto_explain",
            "-c",
            "cron.database_name=postgres",
            "-c",
            "cron.use_background_workers=on",
            "-c",
            "max_worker_processes=24",
        ],
        ports=[docker.ContainerPortArgs(internal=5432, external=infra.db_port, ip="127.0.0.1")],
        volumes=[docker.ContainerVolumeArgs(volume_name=pg_data.name, container_path="/var/lib/postgresql")],
        networks_advanced=[docker.ContainerNetworksAdvancedArgs(name=network.name, aliases=["db"])],
        healthcheck=docker.ContainerHealthcheckArgs(
            tests=["CMD", "pg_isready", "-U", "maghz", "-d", "maghz", "-q"], interval="10s", timeout="5s", retries=5, start_period="30s"
        ),
        opts=pulumi.ResourceOptions.merge(on, pulumi.ResourceOptions(depends_on=[image])),  # gate on the image build, over the shared provider opts
    )

    docker.Container(
        "n8n",
        name=cfg.n8n.container_name,
        image=cfg.n8n.image,
        restart="unless-stopped",
        envs=[
            f"N8N_ENCRYPTION_KEY_FILE={cfg.n8n.encryption_key_file}",
            "DB_TYPE=postgresdb",
            "DB_POSTGRESDB_HOST=db",  # the Docker network alias owned by the `db` container's aliases=["db"]
            "DB_POSTGRESDB_PORT=5432",
            "DB_POSTGRESDB_DATABASE=n8n",
            "DB_POSTGRESDB_USER=maghz",
            "NODE_ENV=production",
            f"N8N_HOST={cfg.n8n.host}",
            f"N8N_PROTOCOL={cfg.n8n.protocol}",
            f"WEBHOOK_URL={cfg.n8n.webhook_url}",
            f"N8N_PROXY_HOPS={cfg.n8n.proxy_hops}",
            "GENERIC_TIMEZONE=UTC",
        ],
        # HTTPS hands the public port to the reverse proxy on the `maghz` network; the `n8n` alias is the only ingress.
        ports=[docker.ContainerPortArgs(internal=5678, external=cfg.n8n.port, ip="127.0.0.1")] if cfg.n8n.protocol == "http" else [],
        volumes=[
            docker.ContainerVolumeArgs(volume_name=n8n_data.name, container_path="/home/node/.n8n"),
            docker.ContainerVolumeArgs(host_path=str(cfg.n8n.workflows_dir.resolve()), container_path="/home/node/workflows"),
        ],
        networks_advanced=[docker.ContainerNetworksAdvancedArgs(name=network.name, aliases=["n8n"])],
        healthcheck=docker.ContainerHealthcheckArgs(
            tests=["CMD-SHELL", "wget -qO- http://localhost:5678/healthz || exit 1"], interval="15s", timeout="5s", retries=5, start_period="30s"
        ),
        opts=pulumi.ResourceOptions.merge(on, pulumi.ResourceOptions(depends_on=[db_container])),  # gate on db, over the shared provider opts
    )

    pulumi.export("db_dsn", f"postgresql://maghz@127.0.0.1:{infra.db_port}/maghz")
    pulumi.export("ollama_url", f"http://127.0.0.1:{infra.ollama_port}")
    pulumi.export("n8n_url", cfg.n8n.api_url)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["define"]
