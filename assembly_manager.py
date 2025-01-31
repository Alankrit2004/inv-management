from fetch_data import fetch_bom_data, build_bom_tree, display_bom_data, calculate_max_units
from db_connection import connect_to_database


def fetch_all_bom_data(connection):
    """
    Fetches BOM data for all finished goods from the database.
    """
    try:
        cursor = connection.cursor(dictionary=True)  # Ensure data is fetched as dictionaries
        query = """
        SELECT `Code`, `Item-Level`, `Item code`, `Type`, `On-hand Qty`, `Extended Quantity`
        FROM BOM_NEW;
        """
        cursor.execute(query)
        all_bom_data = cursor.fetchall()
        cursor.close()
        return all_bom_data
    except Exception as e:
        print(f"Error fetching BOM data: {e}")
        return []


def extract_purchased_items(all_bom_data):
    """
    Extracts all purchased items from the BOM data.
    """
    purchased_items = [
        row for row in all_bom_data
        if isinstance(row, dict) and row["Type"].lower() == "purchased item"
    ]
    return purchased_items


def filter_purchased_items(purchased_items):
    """
    Filters purchased items with zero on-hand quantity and flags affected finished goods.
    """
    purchased_items_missing = [row for row in purchased_items if row["On-hand Qty"] == 0]

    affected_finished_goods = {}
    for row in purchased_items_missing:
        finished_good = row["Code"]
        item_code = row["Item code"]

        if finished_good not in affected_finished_goods:
            affected_finished_goods[finished_good] = []
        affected_finished_goods[finished_good].append(item_code)

    return purchased_items_missing, affected_finished_goods


def display_craftable_and_missing(connection, all_bom_data):
    """
    Determines which finished goods can and cannot be crafted.
    """
    # Step 1: Extract and filter purchased items
    purchased_items = extract_purchased_items(all_bom_data)
    purchased_items_missing, affected_finished_goods = filter_purchased_items(purchased_items)

    # Display non-craftable finished goods
    if affected_finished_goods:
        print("\nNon-Craftable Finished Goods (Due to Missing Purchased Items):")
        for fg_code, missing_items in affected_finished_goods.items():
            print(f"Finished Good: {fg_code}, Missing Purchased Items: {', '.join(missing_items)}")
    else:
        print("\nNo missing purchased items detected.")

    # Step 2: Identify craftable finished goods
    craftable_goods = []
    finished_goods = {row["Code"] for row in all_bom_data}
    for fg_code in finished_goods - set(affected_finished_goods.keys()):
        bom_data = fetch_bom_data(connection, fg_code)
        if bom_data:
            item_data, tree = build_bom_tree(bom_data, fg_code)
            max_units, _ = calculate_max_units(tree, item_data, fg_code, 1)
            if max_units > 0:
                craftable_goods.append((fg_code, max_units))

    # Display craftable finished goods
    print("\nCraftable Finished Goods:")
    if craftable_goods:
        for fg_code, qty in craftable_goods:
            print(f"Finished Good: {fg_code}, Max Craftable: {qty}")
    else:
        print("No craftable finished goods available.")

    return craftable_goods, affected_finished_goods


def assemble_finished_good(connection, finished_good_code, quantity):
    """
    Simulates and updates the BOM data for the selected finished good.
    Ensures stock does not go below zero during updates.
    """
    bom_data = fetch_bom_data(connection, finished_good_code)
    if not bom_data:
        print(f"No BOM data found for {finished_good_code}. Please try again.")
        return False

    # Build the BOM tree and calculate max craftable units
    item_data, tree = build_bom_tree(bom_data, finished_good_code)
    max_units, shortages = calculate_max_units(tree, item_data, finished_good_code, quantity)

    if max_units < quantity:
        print(f"Cannot assemble {quantity} units of {finished_good_code}. Max craftable: {max_units}.")
        if shortages:
            print("Shortages:", shortages)
        return False

    # Preview stock changes
    print(f"\nSimulated changes for assembling {quantity} units of {finished_good_code}:")
    updates = []
    for item_code, details in item_data.items():
        required_qty = details["Extended Quantity"] * quantity
        available_qty = details["On-hand Qty"]

        # Prevent negative stock values
        new_on_hand_qty = max(0, available_qty - required_qty)
        print(f"{item_code}: On-hand Qty before: {available_qty}, after: {new_on_hand_qty}")
        updates.append((new_on_hand_qty, item_code))

    # Confirm updates
    confirm = input("Confirm changes? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Operation cancelled.")
        return False

    # Update database
    cursor = connection.cursor()
    try:
        for new_qty, item_code in updates:
            cursor.execute("UPDATE BOM_NEW SET `On-hand Qty` = %s WHERE `Item code` = %s;", (new_qty, item_code))
        connection.commit()
        print(f"{quantity} units of {finished_good_code} successfully assembled.")
        return True
    except Exception as e:
        print(f"Database update failed: {e}")
        return False




if __name__ == "__main__":
    connection = connect_to_database()
    if not connection:
        print("Failed to connect to the database.")
        exit()

    # Fetch all BOM data
    all_bom_data = fetch_all_bom_data(connection)
    if not all_bom_data:
        print("No BOM data found.")
        connection.close()
        exit()

    # Step 1: Display craftable and non-craftable finished goods
    display_craftable_and_missing(connection, all_bom_data)

    # Step 2: User interaction for crafting
    while True:
        
        fg_code = input("\nEnter the Finished Good Code to assemble (or type 'exit' to quit): ").strip()
        if fg_code.lower() == "exit":
            break

        try:
            quantity = int(input("Enter the quantity to assemble: ").strip())
            assembled = assemble_finished_good(connection, fg_code, quantity)

            if assembled:
                continue_choice = input("Do you want to create more finished goods? (yes/no): ").strip().lower()
                if continue_choice == "yes":
                    display_craftable_and_missing(connection, all_bom_data)
                    continue
                else:
                    print("Exiting the program.")
                    break
        except ValueError:
            print("Invalid quantity. Please try again.")

    connection.close()
