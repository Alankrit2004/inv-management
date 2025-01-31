from flask import Flask, request, jsonify
from flask_cors import CORS
from fetch_data import fetch_bom_data, build_bom_tree, calculate_max_units
from assembly_manager import fetch_all_bom_data, display_craftable_and_missing, assemble_finished_good
from db_connection import connect_to_database

app = Flask(__name__)
CORS(app)

#Connect to database
connection = connect_to_database()
if not connection:
    print("Failed to connect to database.")
    exit()


@app.route("/get_bom_data", methods=["GET"])
def get_bom_data():
    finished_good_code = request.args.get("finished_good_code")
    if not finished_good_code:
        return jsonify({"error": "Finished good code is required."}), 400
    
    bom_data = fetch_bom_data(connection, finished_good_code)
    if not bom_data:
        return jsonify({"error": "No BOM data found"}), 404
    
    return jsonify({"bom_data": bom_data})


@app.route("/get_craftable_goods", methods=["GET"])
def get_craftable_goods():
    all_bom_data = fetch_all_bom_data(connection)
    craftable_goods, non_craftable_goods = display_craftable_and_missing(connection, all_bom_data)

    return jsonify({"craftable_goods": craftable_goods, "non_craftable_goods": non_craftable_goods})

@app.route("/assemble", methods = ["POST"])
def assemble():
    data = request.get_json()
    finished_good_code = data.get("finished_good_code")
    quantity = data.get("quantity")

    if not finished_good_code or not isinstance(quantity, int) or quantity <= 0:
        return jsonify({"error": "Invalid input data"}), 400
    
    success = assemble_finished_good(connection, finished_good_code, quantity)

    if success:
        return jsonify({"message": f"Successfully assembled {quantity} units of {finished_good_code}."})
    else:
        return jsonify({"error": "Failed to assemble finished good"}), 500
    

if __name__ == "__main__":
    app.run(debug=True)