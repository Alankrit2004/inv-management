from fetch_data import fetch_bom_data, build_bom_tree, calculate_max_units
from db_connection import connect_to_database
from datetime import datetime, timedelta


def fetch_all_bom_data(connection):
    try:
        cursor = connection.cursor(dictionary=True)  
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
   
    purchased_items = [
        row for row in all_bom_data
        if isinstance(row, dict) and row["Type"].lower() == "purchased item"
    ]
    return purchased_items


# def filter_purchased_items(purchased_items):
#     """
#     Filters purchased items with zero on-hand quantity and flags affected finished goods.
#     """
#     purchased_items_missing = [row for row in purchased_items if row["On-hand Qty"] == 0]

#     affected_finished_goods = {}
#     for row in purchased_items_missing:
#         finished_good = row["Code"]
#         item_code = row["Item code"]

#         if finished_good not in affected_finished_goods:
#             affected_finished_goods[finished_good] = []
#         affected_finished_goods[finished_good].append(item_code)

#     return purchased_items_missing, affected_finished_goods


def display_craftable_and_missing(connection, all_bom_data):
    """
    Determines which finished goods can and cannot be crafted.
    Includes missing percentage and estimated dispatch date.
    """
    craftable_goods = []
    non_craftable_goods = []

    # Get all unique finished goods from the BOM
    finished_goods = {row["Code"] for row in all_bom_data}

    for fg_code in finished_goods:
        bom_data = fetch_bom_data(connection, fg_code)
        if bom_data:
            # Build the BOM tree
            item_data, tree = build_bom_tree(bom_data, fg_code)

            # Calculate max craftable units
            max_units, shortages = calculate_max_units(tree, item_data, fg_code, 1)

            # Identify missing items with no children
            missing_items = []
            missing_percentages = []

            for item_code, shortage_qty in shortages:
                if item_code not in tree:  # No children, directly affects production
                    missing_items.append(item_code)

                    # Fetch available stock
                    available_qty = item_data[item_code]["On-hand Qty"]
                    required_qty = item_data[item_code]["Extended Quantity"]

                    # Adjust missing percentage calculation
                    if available_qty > 0:
                        missing_percentage = ((shortage_qty) / (shortage_qty + available_qty)) * 100
                    else:
                        missing_percentage = 100  # Completely missing

                    missing_percentages.append(missing_percentage)

            # Calculate estimated dispatch date
            if missing_items:
                avg_missing_percentage = sum(missing_percentages) / len(missing_percentages) if missing_percentages else 100
                estimated_days = max(1, int(avg_missing_percentage / 10))  # 10% missing → 1 extra day
                estimated_dispatch_date = datetime.today() + timedelta(days=estimated_days)

                non_craftable_goods.append((fg_code, missing_items, avg_missing_percentage, estimated_dispatch_date))
                continue

            # Add to craftable goods if max units > 0
            if max_units > 0:
                craftable_goods.append((fg_code, max_units))

    # Display Non-Craftable Finished Goods with missing percentages and estimated dispatch date
    print("\n🚨 Non-Craftable Finished Goods (Due to Missing Items with No Children):")
    if non_craftable_goods:
        for fg_code, missing_items, missing_percentage, dispatch_date in non_craftable_goods:
            print(f" Finished Good: {fg_code} | Missing Items: {', '.join(missing_items)}")
            print(f"   - Missing Percentage: {missing_percentage:.2f}%")
            print(f"   - Suggested Dispatch Date: {dispatch_date.strftime('%d-%m-%Y')}")
    else:
        print("✅ All finished goods have potential for crafting.")

    # Display Craftable Finished Goods
    print("\n✅ Craftable Finished Goods:")
    if craftable_goods:
        for fg_code, qty in craftable_goods:
            print(f" Finished Good: {fg_code} | Max Craftable: {qty}")
    else:
        print("No craftable finished goods available.")

    return craftable_goods, non_craftable_goods



def assemble_finished_good(connection, finished_good_code, quantity):

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

    while True:
        # Display craftable and non-craftable finished goods
        craftable_goods, non_craftable_goods = display_craftable_and_missing(connection, all_bom_data)

        # Ask the user for the finished good code to assemble
        fg_code = input("\nEnter the Finished Good Code to assemble (or type 'exit' to quit): ").strip()
        if fg_code.lower() == "exit":
            break

        try:
            quantity = int(input("Enter the quantity to assemble: ").strip())
            assembled = assemble_finished_good(connection, fg_code, quantity)

            if assembled:
                continue_choice = input("Do you want to create more finished goods? (yes/no): ").strip().lower()
                if continue_choice == "yes":
                    continue
                else:
                    print("Exiting the program.")
                    break
        except ValueError:
            print("Invalid quantity. Please try again.")

    connection.close()
