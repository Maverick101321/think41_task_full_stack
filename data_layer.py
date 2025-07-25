"""
Data Access Layer
This file contains all the functions that interact directly with the database.
"""
from db import execute_query


def insert_product_template(str_id, name, base_price):
    """Inserts a new product template into the database."""
    sql = "INSERT INTO ProductTemplate (str_id, name, base_price) VALUES (%s, %s, %s) RETURNING template_id, str_id;"
    params = (str_id, name, base_price)
    return execute_query(sql, params, fetch="one")


def find_template_id_by_str_id(template_str_id):
    """Finds a product template's UUID from its string ID."""
    sql = "SELECT template_id FROM ProductTemplate WHERE str_id = %s;"
    return execute_query(sql, (template_str_id,), fetch="one")


def insert_option_category(template_id, str_id, name):
    """Inserts a new option category linked to a template."""
    sql = "INSERT INTO OptionCategory (template_id, str_id, name) VALUES (%s, %s, %s) RETURNING category_id, str_id;"
    params = (template_id, str_id, name)
    return execute_query(sql, params, fetch="one")


def find_category_id_by_str_id(category_str_id):
    """Finds an option category's UUID from its string ID."""
    sql = "SELECT category_id FROM OptionCategory WHERE str_id = %s;"
    return execute_query(sql, (category_str_id,), fetch="one")


def insert_option_choice(category_id, str_id, name, price_delta):
    """Inserts a new option choice linked to a category."""
    sql = "INSERT INTO OptionChoice (category_id, str_id, name, price_delta) VALUES (%s, %s, %s, %s) RETURNING choice_id, str_id;"
    params = (category_id, str_id, name, price_delta)
    return execute_query(sql, params, fetch="one")


def find_choices_for_rule(template_str_id, primary_str_id, secondary_str_id):
    """Finds two choices ensuring they belong to the same product template."""
    sql = """
        SELECT oc.choice_id, oc.str_id
        FROM OptionChoice oc
        JOIN OptionCategory cat ON oc.category_id = cat.category_id
        JOIN ProductTemplate pt ON cat.template_id = pt.template_id
        WHERE pt.str_id = %s AND oc.str_id IN (%s, %s);
    """
    params = (template_str_id, primary_str_id, secondary_str_id)
    return execute_query(sql, params, fetch="all")


def insert_compatibility_rule(rule_type, primary_id, secondary_id):
    """Inserts a new compatibility rule."""
    sql = "INSERT INTO CompatibilityRule (rule_type, primary_choice_id, secondary_choice_id) VALUES (%s, %s, %s) RETURNING rule_id;"
    params = (rule_type, primary_id, secondary_id)
    return execute_query(sql, params, fetch="one")


def find_compatibility_rule_by_id(rule_id):
    """Finds a compatibility rule and its choices by the rule's UUID."""
    sql = """
        SELECT
            cr.rule_id, cr.rule_type,
            pc.str_id AS primary_choice_str_id,
            sc.str_id AS secondary_choice_str_id
        FROM CompatibilityRule cr
        JOIN OptionChoice pc ON cr.primary_choice_id = pc.choice_id
        JOIN OptionChoice sc ON cr.secondary_choice_id = sc.choice_id
        WHERE cr.rule_id = %s;
    """
    return execute_query(sql, (str(rule_id),), fetch="one")


def find_target_choices(template_str_id, category_str_id):
    """Finds all choices for a given category within a template."""
    sql = """
        SELECT oc.choice_id, oc.str_id, oc.name, oc.price_delta, oc.category_id
        FROM OptionChoice oc
        JOIN OptionCategory ocat ON oc.category_id = ocat.category_id
        JOIN ProductTemplate pt ON ocat.template_id = pt.template_id
        WHERE pt.str_id = %s AND ocat.str_id = %s;
    """
    return execute_query(sql, (template_str_id, category_str_id), fetch="all")


def find_selected_choice_uuids(selection_pairs):
    """Finds the UUIDs of currently selected choices."""
    sql = """
        SELECT oc.choice_id FROM OptionChoice oc
        JOIN OptionCategory ocat ON oc.category_id = ocat.category_id
        WHERE (ocat.str_id, oc.str_id) IN %s;
    """
    return execute_query(sql, (tuple(selection_pairs),), fetch="all")


def find_incompatible_uuids(selected_uuids):
    """Finds all choice UUIDs that are incompatible with the current selection."""
    sql = """
        SELECT primary_choice_id AS choice_id FROM CompatibilityRule WHERE rule_type = 'INCOMPATIBLE_WITH' AND secondary_choice_id = ANY(%s)
        UNION
        SELECT secondary_choice_id AS choice_id FROM CompatibilityRule WHERE rule_type = 'INCOMPATIBLE_WITH' AND primary_choice_id = ANY(%s);
    """
    results = execute_query(sql, (selected_uuids, selected_uuids), fetch="all")
    return {row['choice_id'] for row in results}


def find_required_choices(selected_uuids):
    """Finds all choices that are required by the current selection."""
    sql = """
        SELECT cr.secondary_choice_id, oc.category_id
        FROM CompatibilityRule cr JOIN OptionChoice oc ON cr.secondary_choice_id = oc.choice_id
        WHERE cr.rule_type = 'REQUIRES' AND cr.primary_choice_id = ANY(%s);
    """
    return execute_query(sql, (selected_uuids,), fetch="all")