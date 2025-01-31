import mysql.connector
import json
from collections import defaultdict

def fetch_bom_data(connection, finished_good_code):
    try:
        cursor = connection.cursor(dictionary=True)
        query = """
        WITH RECURSIVE BOM_Tree AS (
            SELECT `Code`, `Item-Level`, `Item code`, `Type`, `On-hand Qty`, `Extended Quantity`
            FROM BOM_NEW
            WHERE `Code` = %s
            
            UNION ALL
            
            SELECT b.`Code`, b.`Item-Level`, b.`Item code`, b.`Type`, b.`On-hand Qty`, b.`Extended Quantity`
            FROM BOM_NEW b
            INNER JOIN BOM_Tree bt ON b.`Code` = bt.`Item code`
        )
        SELECT * FROM BOM_Tree;
        """
        cursor.execute(query, (finished_good_code,))
        bom_data = cursor.fetchall()
        cursor.close()
        return bom_data
    except mysql.connector.Error as e:
        print(f"Error fetching BOM data: {e}")
        return []

def build_bom_tree(bom_data, finished_good_code):
  
    item_data = {row["Item code"]: row for row in bom_data}
    tree = defaultdict(list)
    parent_stack = []  # Track the last-seen parent for each level

   
    if finished_good_code not in item_data:
        item_data[finished_good_code] = {
            "On-hand Qty": 0,
            "Extended Quantity": 1,  
            "Type": "finished_good",
            "Item-Level": 0
        }

    for row in bom_data:
        item_code = row["Item code"]
        level = row["Item-Level"]

        # Adjust parent stack based on the current level
        while parent_stack and parent_stack[-1][1] >= level:
            parent_stack.pop()

        # If there's a parent in the stack, establish the relationship
        if parent_stack:
            parent = parent_stack[-1][0]
            tree[parent].append(item_code)

        # Add the current item to the stack
        parent_stack.append((item_code, level))

    # Add all Level 1 items as children of the finished good code
    for row in bom_data:
        if row["Item-Level"] == 1:
            tree[finished_good_code].append(row["Item code"])

    return item_data, tree


def export_tree_to_json(tree, filename="bom_tree.json"):
    """
    Exports the tree structure to a JSON file for inspection.
    Args:
        tree: The tree dictionary (parent -> [children]).
        filename: The name of the output JSON file.
    """
    with open(filename, "w") as json_file:
        json.dump(tree, json_file, indent=4)
    print(f"Tree exported to {filename}")



def display_bom_data(bom_data):
    print("\nBOM Data:")
    print("{:<15} {:<10} {:<20} {:<15} {:<10} {:<15}".format(
        "Code", "Item-Level", "Item code", "Type", "On-hand Qty", "Extended Quantity"
    ))
    print("-" * 85)
    for row in bom_data:
        print("{:<15} {:<10} {:<20} {:<15} {:<10} {:<15}".format(
            row["Code"], row["Item-Level"], row["Item code"], row["Type"],
            row["On-hand Qty"], row["Extended Quantity"]
        ))

def calculate_max_units(tree, item_data, finished_good_code, required_quantity):
    """
    Calculates the maximum craftable units of a finished good while ensuring stock constraints are respected.
    """
    shortages = []  # Track items causing shortages

    def recursive_calculate(item_code, quantity_needed):
        if item_code not in item_data:
            shortages.append((item_code, "Unknown"))
            return 0

        item = item_data[item_code]
        on_hand_qty = item["On-hand Qty"]
        required_qty = item["Extended Quantity"]
        item_type = item["Type"].lower()

        # Root node availability
        # print(f"\nProcessing '{item_code}' (Type: {item_type}) - Needed: {quantity_needed}, Available: {on_hand_qty}")

        # Purchased items must stop the process if insufficient
        if item_type == "purchased item":
            if on_hand_qty < quantity_needed:
                shortages.append((item_code, quantity_needed - on_hand_qty))
                return 0
            return on_hand_qty // required_qty if required_qty > 0 else float("inf")

        # If sufficient stock exists, no further traversal required
        if on_hand_qty >= quantity_needed:
            return on_hand_qty // required_qty if required_qty > 0 else float("inf")

        # Traverse children only if parent stock is insufficient
        if item_code in tree:
            child_units = []
            for child in tree[item_code]:
                child_quantity_needed = quantity_needed * item_data[child]["Extended Quantity"]
                units = recursive_calculate(child, child_quantity_needed)
                if units == 0:
                    return 0
                child_units.append(units)
            return min(child_units) if child_units else float("inf")

        # Leaf node with insufficient stock
        if on_hand_qty < quantity_needed:
            shortages.append((item_code, quantity_needed - on_hand_qty))
            return 0

        return on_hand_qty // required_qty if required_qty > 0 else float("inf")

    max_units = recursive_calculate(finished_good_code, required_quantity)
    return max_units, shortages
