from flask import Flask, request, jsonify
import psycopg2
import data_layer
from db import init_app

# Initialize the Flask application
app = Flask(__name__)

# Load configuration from config.py
app.config.from_object('config.Config')

# Register database functions with the app
init_app(app)

@app.route('/')
def index():
    return "Welcome to the Product Configurator API!"

# --- API Endpoints ---

# 1. POST /product-templates
@app.route('/product-templates', methods=['POST'])
def create_product_template():
    """Creates a new product template."""
    data = request.get_json()
    # Updated to match the problem statement's API contract
    if not data or 'template_str_id' not in data or 'name' not in data or 'base_price' not in data:
        return jsonify({"error": "Request must include 'template_str_id', 'name', and 'base_price'"}), 400

    try:
        new_template = data_layer.insert_product_template(
            data['template_str_id'], data['name'], data['base_price'])
        return jsonify({"template_id": str(new_template['template_id']), "template_str_id": new_template['str_id']}), 201
    except psycopg2.Error as e:
        # Handle potential conflicts, e.g., unique name violation
        return jsonify({"error": "Database error", "detail": str(e)}), 409

# 2. POST /product-templates/<template_str_id>/option-categories
@app.route('/product-templates/<string:template_str_id>/option-categories', methods=['POST'])
def create_option_category(template_str_id):
    """Adds an option category to a specific product template."""
    data = request.get_json()
    if not data or 'category_str_id' not in data or 'name' not in data:
        return jsonify({"error": "Request must include 'category_str_id' and 'name'"}), 400

    try:
        # First, find the template's UUID from its str_id
        template = data_layer.find_template_id_by_str_id(template_str_id)
        if not template:
            return jsonify({"error": f"Product template with id '{template_str_id}' not found."}), 404

        new_category = data_layer.insert_option_category(
            template['template_id'], data['category_str_id'], data['name'])

        return jsonify({"category_id": str(new_category['category_id']), "category_str_id": new_category['str_id']}), 201
    except psycopg2.Error as e:
        # This can fail if template_id doesn't exist or if the category name is a duplicate for this template.
        return jsonify({"error": "Database error", "detail": str(e)}), 409

# 3. POST /option-categories/<category_str_id>/choices
@app.route('/option-categories/<string:category_str_id>/choices', methods=['POST'])
def create_option_choice(category_str_id):
    """Adds a specific choice to an option category."""
    data = request.get_json()
    if not data or 'choice_str_id' not in data or 'name' not in data or 'price_delta' not in data:
        return jsonify({"error": "Request must include 'choice_str_id', 'name', and 'price_delta'"}), 400

    try:
        # First, find the category's UUID from its str_id
        # Note: category str_ids are only unique per template, but we'll assume for now they are globally unique for this endpoint.
        # A more robust solution might be /product-templates/{tid}/categories/{cid}/choices
        category = data_layer.find_category_id_by_str_id(category_str_id)
        if not category:
            return jsonify({"error": f"Option category with id '{category_str_id}' not found."}), 404

        new_choice = data_layer.insert_option_choice(
            category['category_id'], data['choice_str_id'], data['name'], data['price_delta'])

        return jsonify({"choice_id": str(new_choice['choice_id']), "choice_str_id": new_choice['str_id']}), 201
    except psycopg2.Error as e:
        # This can fail if category_id doesn't exist or if the choice name is a duplicate for this category.
        return jsonify({"error": "Database error", "detail": str(e)}), 409

# --- Milestone 1: Add Compatibility Rule ---
@app.route('/product-templates/<string:template_str_id>/compatibility-rules', methods=['POST'])
def create_compatibility_rule(template_str_id):
    """Creates a compatibility rule between two option choices within a template."""
    data = request.get_json()
    required_fields = ['rule_type', 'primary_choice_str_id', 'secondary_choice_str_id']
    if not data or not all(field in data for field in required_fields):
        return jsonify({"error": f"Request must include {', '.join(required_fields)}"}), 400

    rule_type = data['rule_type']
    primary_choice_str_id = data['primary_choice_str_id']
    secondary_choice_str_id = data['secondary_choice_str_id']

    if rule_type not in ('REQUIRES', 'INCOMPATIBLE_WITH'):
        return jsonify({"error": "rule_type must be 'REQUIRES' or 'INCOMPATIBLE_WITH'"}), 400

    if primary_choice_str_id == secondary_choice_str_id:
        return jsonify({"error": "A choice cannot have a compatibility rule with itself."}), 400

    try:
        # This query ensures both choices exist and belong to the specified product template.
        # It's a crucial validation step to prevent creating rules across different products.
        choices = data_layer.find_choices_for_rule(
            template_str_id, primary_choice_str_id, secondary_choice_str_id)

        if len(choices) != 2:
            return jsonify({"error": "One or both choice IDs are invalid or do not belong to this product template."}), 404

        # Map str_ids back to the UUIDs found in the database
        choice_map = {choice['str_id']: choice['choice_id'] for choice in choices}
        primary_choice_id = choice_map[primary_choice_str_id]
        secondary_choice_id = choice_map[secondary_choice_str_id]

        # Insert the rule
        new_rule = data_layer.insert_compatibility_rule(
            rule_type, primary_choice_id, secondary_choice_id)

        return jsonify({"message": "Compatibility rule added successfully.", "rule_id": str(new_rule['rule_id'])}), 201

    except psycopg2.Error as e:
        return jsonify({"error": "Database error", "detail": str(e)}), 409

@app.route('/compatibility-rules/<uuid:rule_id>', methods=['GET'])
def get_compatibility_rule(rule_id):
    """Retrieves a specific compatibility rule by its UUID."""
    try:
        rule = data_layer.find_compatibility_rule_by_id(rule_id)

        if not rule:
            return jsonify({"error": "Compatibility rule not found."}), 404

        return jsonify(dict(rule))
    except psycopg2.Error as e:
        return jsonify({"error": "Database error", "detail": str(e)}), 500

# --- Milestone 2: Get Available Options ---
@app.route('/product-templates/<string:template_str_id>/available-options/<string:target_category_str_id>', methods=['POST'])
def get_available_options(template_str_id, target_category_str_id):
    """
    Based on current selections and compatibility rules, returns a list of
    valid OptionChoices for a target category.
    """
    data = request.get_json()
    if not data:
        data = {}

    current_selections = data.get('current_selections', {})

    try:
        # 1. Get all choices for the target category. This is our potential result set.
        target_choices = data_layer.find_target_choices(
            template_str_id, target_category_str_id)

        if not target_choices:
            # This could mean the template or category is invalid, or the category is empty.
            # A check could be added to see if the category exists at all.
            return jsonify([])

        # If there are no selections, all choices in the category are available.
        if not current_selections:
            return jsonify([dict(row) for row in target_choices])

        # 2. Get the UUIDs of the currently selected choices.
        # We build a list of tuples for the IN clause
        selection_pairs = [(k, v) for k, v in current_selections.items()]
        selected_results = data_layer.find_selected_choice_uuids(selection_pairs)
        selected_uuids = [row['choice_id'] for row in selected_results]

        if not selected_uuids:
            return jsonify([dict(row) for row in target_choices]) # Invalid selections, return all

        # 3. Find all choices that are INCOMPATIBLE with the current selections.
        incompatible_uuids = data_layer.find_incompatible_uuids(selected_uuids)

        # 4. Find all choices that are REQUIRED by the current selections.
        required_results = data_layer.find_required_choices(selected_uuids)

        # 5. Filter the initial list of target choices based on the rules.
        target_category_id = target_choices[0]['category_id']
        required_in_target_category = {row['secondary_choice_id'] for row in required_results if row['category_id'] == target_category_id}

        available_options = []
        for choice in target_choices:
            # A choice is invalid if it's in the incompatible list.
            if choice['choice_id'] in incompatible_uuids:
                continue
            # If this category has requirements, a choice is only valid if it's one of them.
            if required_in_target_category and choice['choice_id'] not in required_in_target_category:
                continue
            available_options.append({"str_id": choice['str_id'], "name": choice['name'], "price_delta": float(choice['price_delta'])})

        return jsonify(available_options)

    except psycopg2.Error as e:
        return jsonify({"error": "Database error", "detail": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)