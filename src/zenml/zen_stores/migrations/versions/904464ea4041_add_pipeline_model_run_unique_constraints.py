"""Add pipeline, model and run unique constraints [904464ea4041].

Revision ID: 904464ea4041
Revises: b557b2871693
Create Date: 2024-11-04 10:27:05.450092

"""

from collections import defaultdict
from typing import Any, Dict, Set

import sqlalchemy as sa
from alembic import op

from zenml.logger import get_logger

logger = get_logger(__name__)

# revision identifiers, used by Alembic.
revision = "904464ea4041"
down_revision = "b557b2871693"
branch_labels = None
depends_on = None


def resolve_duplicate_entities() -> None:
    """Resolve duplicate entities."""
    connection = op.get_bind()
    meta = sa.MetaData()
    meta.reflect(
        bind=connection,
        only=("pipeline_run", "pipeline", "model", "model_version"),
    )

    # Remove duplicate names for runs, pipelines and models
    for table_name in ["pipeline_run", "pipeline", "model"]:
        table = sa.Table(table_name, meta)
        result = connection.execute(
            sa.select(table.c.id, table.c.name, table.c.workspace_id)
        ).all()
        existing: Dict[str, Set[str]] = defaultdict(set)

        for id_, name, workspace_id in result:
            names_in_workspace = existing[workspace_id]

            if name in names_in_workspace:
                new_name = f"{name}_{id_[:6]}"
                logger.warning(
                    "Migrating %s name from %s to %s to resolve duplicate name.",
                    table_name,
                    name,
                    new_name,
                )
                connection.execute(
                    sa.update(table)
                    .where(table.c.id == id_)
                    .values(name=new_name)
                )
                names_in_workspace.add(new_name)
            else:
                names_in_workspace.add(name)

    # Remove duplicate names and version numbers for model versions
    model_version_table = sa.Table("model_version", meta)
    result = connection.execute(
        sa.select(
            model_version_table.c.id,
            model_version_table.c.name,
            model_version_table.c.number,
            model_version_table.c.model_id,
        )
    ).all()

    existing_names: Dict[str, Set[str]] = defaultdict(set)
    existing_numbers: Dict[str, Set[int]] = defaultdict(set)

    needs_update = []

    for id_, name, number, model_id in result:
        names_for_model = existing_names[model_id]
        numbers_for_model = existing_numbers[model_id]

        needs_new_name = name in names_for_model
        needs_new_number = number in numbers_for_model

        if needs_new_name or needs_new_number:
            needs_update.append(
                (id_, name, number, model_id, needs_new_name, needs_new_number)
            )

        names_for_model.add(name)
        numbers_for_model.add(number)

    for (
        id_,
        name,
        number,
        model_id,
        needs_new_name,
        needs_new_number,
    ) in needs_update:
        values: Dict[str, Any] = {}

        is_numeric_version = str(number) == name
        next_numeric_version = max(existing_numbers[model_id]) + 1

        if is_numeric_version:
            # No matter if the name or number clashes, we need to update both
            values["number"] = next_numeric_version
            values["name"] = str(next_numeric_version)
            existing_numbers[model_id].add(next_numeric_version)
            logger.warning(
                "Migrating model version %s to %s to resolve duplicate name.",
                name,
                values["name"],
            )
        else:
            if needs_new_name:
                values["name"] = f"{name}_{id_[:6]}"
                logger.warning(
                    "Migrating model version %s to %s to resolve duplicate name.",
                    name,
                    values["name"],
                )

            if needs_new_number:
                values["number"] = next_numeric_version
                existing_numbers[model_id].add(next_numeric_version)

        connection.execute(
            sa.update(model_version_table)
            .where(model_version_table.c.id == id_)
            .values(**values)
        )


def upgrade() -> None:
    """Upgrade database schema and/or data, creating a new revision."""
    # ### commands auto generated by Alembic - please adjust! ###

    resolve_duplicate_entities()

    with op.batch_alter_table("pipeline", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "unique_pipeline_name_in_workspace", ["name", "workspace_id"]
        )

    with op.batch_alter_table("pipeline_run", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "unique_run_name_in_workspace", ["name", "workspace_id"]
        )

    with op.batch_alter_table("model", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "unique_model_name_in_workspace", ["name", "workspace_id"]
        )

    with op.batch_alter_table("model_version", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "unique_version_for_model_id", ["name", "model_id"]
        )
        batch_op.create_unique_constraint(
            "unique_version_number_for_model_id", ["number", "model_id"]
        )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade database schema and/or data back to the previous revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("model_version", schema=None) as batch_op:
        batch_op.drop_constraint(
            "unique_version_number_for_model_id", type_="unique"
        )
        batch_op.drop_constraint("unique_version_for_model_id", type_="unique")

    with op.batch_alter_table("model", schema=None) as batch_op:
        batch_op.drop_constraint(
            "unique_model_name_in_workspace", type_="unique"
        )

    with op.batch_alter_table("pipeline_run", schema=None) as batch_op:
        batch_op.drop_constraint(
            "unique_run_name_in_workspace", type_="unique"
        )

    with op.batch_alter_table("pipeline", schema=None) as batch_op:
        batch_op.drop_constraint(
            "unique_pipeline_name_in_workspace", type_="unique"
        )

    # ### end Alembic commands ###
