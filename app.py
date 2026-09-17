"""
Household app - shared shopping list, household tasks and grocery stock
monitoring for two people.

I built this as a single Streamlit page with a sidebar to switch between the
three sections, backed by a local SQLite file (household.db, created next to
this script the first time it runs). It's meant to be run on one machine
(my Mac) and opened from both our phones over wifi - see the "How to run"
notes I sent alongside this file.
"""

from datetime import date, timedelta

import streamlit as st

import db

st.set_page_config(page_title="Our Household", page_icon="🏠", layout="centered")

db.init_db()

CATEGORIES = [
    "Fruit & Veg",
    "Meat & Fish",
    "Dairy & Eggs",
    "Bakery",
    "Frozen",
    "Store Cupboard",
    "Drinks",
    "Household",
    "Toiletries",
    "Other",
]

UNITS = ["pcs", "pack", "kg", "g", "litres", "ml", "box"]

STORES = ["Lidl", "Morrisons", "Tesco", "Home Bargains", "Boots", "Primark", "Any / no preference"]

# Starter pantry list - (name, category, unit, preferred_store). I pulled the
# Lidl entries straight from 16 of our actual receipts (what shows up again
# and again is what I've kept - one-off buys aren't worth tracking as a
# staple), and added the Tesco/Home Bargains/Morrisons items Yusuf named from
# memory. Wired up as a one-click "load" rather than a script, since this has
# to stay usable for my wife without ever touching a terminal.
STARTER_ITEMS = [
    # Lidl - meat
    ("Chicken Thighs", "Meat & Fish", "kg", "Lidl"),
    ("Chicken Legs", "Meat & Fish", "kg", "Lidl"),
    ("Chicken Drumsticks", "Meat & Fish", "kg", "Lidl"),
    ("Chicken Wings", "Meat & Fish", "kg", "Lidl"),
    # Lidl - fruit & veg
    ("Potatoes", "Fruit & Veg", "kg", "Lidl"),
    ("Sweet Potatoes", "Fruit & Veg", "kg", "Lidl"),
    ("Onions", "Fruit & Veg", "pack", "Lidl"),
    ("Carrots", "Fruit & Veg", "pack", "Lidl"),
    ("Red Gala Apples", "Fruit & Veg", "pack", "Lidl"),
    ("Bananas", "Fruit & Veg", "pack", "Lidl"),
    ("Iceberg Lettuce", "Fruit & Veg", "pcs", "Lidl"),
    ("Curly Kale", "Fruit & Veg", "pack", "Lidl"),
    ("Washed Baby Spinach", "Fruit & Veg", "pack", "Lidl"),
    ("Tomatoes", "Fruit & Veg", "pack", "Lidl"),
    ("Red Pepper", "Fruit & Veg", "pack", "Lidl"),
    ("Grapes", "Fruit & Veg", "pack", "Lidl"),
    ("Sweetcorn", "Fruit & Veg", "pack", "Lidl"),
    # Lidl - drinks / store cupboard / bakery / dairy
    ("Apple Juice", "Drinks", "litres", "Lidl"),
    ("Chocolate Protein Drink", "Drinks", "pcs", "Lidl"),
    ("Colombian Coffee", "Drinks", "pack", "Lidl"),
    ("High Protein Wraps", "Store Cupboard", "pack", "Lidl"),
    ("Tortilla Wraps", "Store Cupboard", "pack", "Lidl"),
    ("Spaghetti", "Store Cupboard", "pack", "Lidl"),
    ("Tomato Puree", "Store Cupboard", "pcs", "Lidl"),
    ("Salad Cream", "Store Cupboard", "pcs", "Lidl"),
    ("Frying Oil", "Store Cupboard", "litres", "Lidl"),
    ("Natural Yogurt", "Dairy & Eggs", "pack", "Lidl"),
    ("Brioche Loaf", "Bakery", "pcs", "Lidl"),
    ("Butter Croissants", "Bakery", "pack", "Lidl"),
    # Lidl - household
    ("Washing Up Liquid", "Household", "pcs", "Lidl"),
    ("Kitchen Towel", "Household", "pack", "Lidl"),
    ("Toilet Tissue", "Household", "pack", "Lidl"),
    ("Dishwasher Capsules", "Household", "pack", "Lidl"),
    ("Batteries AAA", "Household", "pack", "Lidl"),
    # Tesco (named from memory)
    ("Rice", "Store Cupboard", "pack", "Tesco"),
    ("Mixed Veggies", "Frozen", "pack", "Tesco"),  # flagged as maybe-Lidl instead - check this one
    ("Chicken Frankfurters", "Meat & Fish", "pack", "Tesco"),
    ("Baby Wipes (Fred & Flo)", "Toiletries", "pack", "Tesco"),
    ("Nappies (Fred & Flo)", "Toiletries", "pack", "Tesco"),
    ("Weetabix", "Store Cupboard", "box", "Tesco"),
    # Morrisons - confirmed against 4 actual Morrisons receipts. Cravendale
    # Milk and Fruit Shoot showed up in 3 of the 4; Kendamil Formula, M
    # Doughnuts, the Sweetclem/foil/apple juice/apples/Red Bull/popcorn on
    # the third receipt each appeared exactly once, so I've left those out
    # as one-off buys rather than regulars - same rule I used for Lidl.
    ("Cravendale Milk", "Dairy & Eggs", "litres", "Morrisons"),
    ("Cerelac Fruit Cereal", "Other", "box", "Morrisons"),
    ("Fruit Shoot", "Drinks", "pcs", "Morrisons"),
    # Home Bargains
    ("Air Wick Plug-In", "Household", "pcs", "Home Bargains"),
    ("Febreze Lenor Air Freshener", "Household", "pcs", "Home Bargains"),
    ("Febreze Plug-In Air Freshener", "Household", "pcs", "Home Bargains"),
]

# A small set of everyday words people type instead of a receipt-exact name
# ("bread" vs "Brioche Loaf"). Used by guess_category() below so the
# category dropdown doesn't have to be set by hand for common items.
CATEGORY_KEYWORDS = {
    "bread": "Bakery", "loaf": "Bakery", "croissant": "Bakery", "bagel": "Bakery",
    "milk": "Dairy & Eggs", "cheese": "Dairy & Eggs", "yogurt": "Dairy & Eggs",
    "yoghurt": "Dairy & Eggs", "butter": "Dairy & Eggs", "eggs": "Dairy & Eggs", "egg": "Dairy & Eggs",
    "chicken": "Meat & Fish", "beef": "Meat & Fish", "fish": "Meat & Fish", "mackerel": "Meat & Fish",
    "bacon": "Meat & Fish", "sausage": "Meat & Fish", "mince": "Meat & Fish",
    "apple": "Fruit & Veg", "banana": "Fruit & Veg", "orange": "Fruit & Veg", "tomato": "Fruit & Veg",
    "potato": "Fruit & Veg", "onion": "Fruit & Veg", "carrot": "Fruit & Veg", "pepper": "Fruit & Veg",
    "lettuce": "Fruit & Veg", "spinach": "Fruit & Veg", "grape": "Fruit & Veg",
    "juice": "Drinks", "water": "Drinks", "coffee": "Drinks", "tea": "Drinks", "cola": "Drinks",
    "rice": "Store Cupboard", "pasta": "Store Cupboard", "spaghetti": "Store Cupboard", "flour": "Store Cupboard",
    "toilet": "Toiletries", "tissue": "Toiletries", "shampoo": "Toiletries", "soap": "Toiletries",
    "nappies": "Toiletries", "nappy": "Toiletries", "wipes": "Toiletries",
    "washing up": "Household", "dishwasher": "Household", "kitchen towel": "Household",
    "air freshener": "Household", "batteries": "Household",
    "frozen": "Frozen", "peas": "Frozen", "veggies": "Frozen",
}


def guess_category(item_name):
    """Best-effort category guess from a typed item name, so nobody has to
    think about categories for everyday items. Checks the starter list first
    (exact name match), then falls back to the keyword list above. Returns
    None if nothing matches, so the caller falls back to the manual dropdown.
    """
    name = item_name.strip().lower()
    if not name:
        return None
    for starter_name, starter_category, _, _ in STARTER_ITEMS:
        if starter_name.lower() == name:
            return starter_category
    for keyword, keyword_category in CATEGORY_KEYWORDS.items():
        if keyword in name:
            return keyword_category
    return None


# ---------------------------------------------------------------------------
# Sidebar: who's using the app, and page navigation
# ---------------------------------------------------------------------------

st.sidebar.title("🏠 Our Household")

with st.sidebar.expander("Names", expanded=False):
    name_a = st.text_input("Your name", value=st.session_state.get("name_a", "Yusuf"))
    name_b = st.text_input("Partner's name", value=st.session_state.get("name_b", "Wife"))
    st.session_state["name_a"] = name_a
    st.session_state["name_b"] = name_b

current_user = st.sidebar.radio("Who's this?", [name_a, name_b], horizontal=True)

page = st.sidebar.radio(
    "Go to",
    ["🛒 Shopping List", "✅ Household Tasks", "📦 Grocery Stock"],
)

st.sidebar.divider()
low_stock_count = len(db.get_low_stock_items())
if low_stock_count:
    st.sidebar.warning(f"{low_stock_count} item(s) running low - check Grocery Stock")


# ---------------------------------------------------------------------------
# Shopping list
# ---------------------------------------------------------------------------

def render_shopping_list():
    st.header("🛒 Shopping List")

    with st.form("add_shopping_item", clear_on_submit=True):
        cols = st.columns([3, 1, 2])
        item_name = cols[0].text_input("Item")
        quantity = cols[1].text_input("Qty", placeholder="e.g. 2")
        category = cols[2].selectbox("Category", CATEGORIES)
        submitted = st.form_submit_button("Add to list")
        if submitted:
            if item_name.strip():
                final_category = guess_category(item_name) or category
                db.add_shopping_item(item_name, quantity, final_category, current_user)
                st.rerun()
            else:
                st.warning("Give the item a name first.")

    items = db.get_shopping_list()
    if not items:
        st.info("Nothing on the list right now.")
    else:
        by_category = {}
        for item in items:
            by_category.setdefault(item["category"], []).append(item)

        for category in CATEGORIES:
            if category not in by_category:
                continue
            st.subheader(category)
            for item in by_category[category]:
                c1, c2, c3 = st.columns([0.6, 3, 0.7])
                bought = c1.checkbox("Bought", key=f"buy_{item['id']}", label_visibility="collapsed")
                label = item["item_name"]
                if item["quantity"]:
                    label += f"  ·  {item['quantity']}"
                label += f"  ·  _added by {item['added_by']}_"
                c2.markdown(label)
                if c3.button("🗑", key=f"del_shop_{item['id']}"):
                    db.delete_shopping_item(item["id"])
                    st.rerun()
                if bought:
                    db.mark_shopping_item(item["id"], current_user, bought=True)
                    st.rerun()

    bought_items = db.get_shopping_list(include_bought=True)
    bought_items = [i for i in bought_items if i["is_bought"]]
    if bought_items:
        with st.expander(f"Bought ({len(bought_items)})"):
            for item in bought_items:
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"~~{item['item_name']}~~  ·  _by {item['bought_by']}_")
                if c2.button("Undo", key=f"undo_{item['id']}"):
                    db.mark_shopping_item(item["id"], current_user, bought=False)
                    st.rerun()
            if st.button("Clear bought items"):
                db.clear_bought_items()
                st.rerun()


# ---------------------------------------------------------------------------
# Household tasks
# ---------------------------------------------------------------------------

def render_tasks():
    st.header("✅ Household Tasks")

    with st.form("add_task", clear_on_submit=True):
        title = st.text_input("Task")
        notes = st.text_area("Notes (optional)", height=68)
        cols = st.columns(2)
        assigned_to = cols[0].selectbox("Assign to", [current_user, name_a if current_user != name_a else name_b, "Either"])
        has_due = cols[1].checkbox("Set a due date")
        due_date = None
        if has_due:
            due_date = st.date_input("Due date", value=date.today() + timedelta(days=1))
        submitted = st.form_submit_button("Add task")
        if submitted:
            if title.strip():
                db.add_task(title, notes, assigned_to, due_date, current_user)
                st.rerun()
            else:
                st.warning("Give the task a title first.")

    pending = db.get_tasks(status="pending")
    st.subheader(f"To do ({len(pending)})")
    if not pending:
        st.info("Nothing outstanding. Nice.")
    today = date.today()
    for task in pending:
        c1, c2, c3 = st.columns([0.6, 3.5, 0.6])
        done = c1.checkbox("Done", key=f"done_{task['id']}", label_visibility="collapsed")
        label = f"**{task['title']}**  ·  _{task['assigned_to']}_"
        if task["due_date"]:
            due = date.fromisoformat(task["due_date"])
            if due < today:
                label += f"  ·  :red[overdue {due.strftime('%d %b')}]"
            else:
                label += f"  ·  due {due.strftime('%d %b')}"
        c2.markdown(label)
        if task["notes"]:
            c2.caption(task["notes"])
        if c3.button("🗑", key=f"del_task_{task['id']}"):
            db.delete_task(task["id"])
            st.rerun()
        if done:
            db.set_task_status(task["id"], "done")
            st.rerun()

    done_tasks = db.get_tasks(status="done")
    if done_tasks:
        with st.expander(f"Done ({len(done_tasks)})"):
            for task in done_tasks:
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"~~{task['title']}~~  ·  _{task['assigned_to']}_")
                if c2.button("Reopen", key=f"reopen_{task['id']}"):
                    db.set_task_status(task["id"], "pending")
                    st.rerun()


# ---------------------------------------------------------------------------
# Grocery stock monitoring
# ---------------------------------------------------------------------------

def render_stock():
    st.header("📦 Grocery Stock")
    st.caption("Track pantry staples so you know what's running low before you're out.")

    low_stock = db.get_low_stock_items()
    if low_stock:
        st.subheader(f"⚠️ Running low ({len(low_stock)})")
        for item in low_stock:
            c1, c2 = st.columns([3, 1.4])
            c1.markdown(f"**{item['name']}**  ·  {item['current_stock']:g} {item['unit']} left (threshold {item['low_stock_threshold']:g})")
            if item["preferred_store"]:
                c1.caption(f"Usually get this from {item['preferred_store']}")
            if db.is_item_already_on_shopping_list(item["id"]):
                c2.caption("Already on list ✓")
            else:
                if c2.button("Add to list", key=f"restock_{item['id']}"):
                    db.add_shopping_item(item["name"], "", item["category"], current_user, pantry_item_id=item["id"])
                    st.rerun()
        st.divider()

    existing_names = db.get_pantry_item_names()
    not_yet_loaded = [i for i in STARTER_ITEMS if i[0] not in existing_names]
    if not_yet_loaded:
        if st.button(f"📋 Load our usual items ({len(not_yet_loaded)} not yet added)"):
            added = db.seed_pantry_items(STARTER_ITEMS)
            st.success(f"Added {added} item(s) from our regular shop.")
            st.rerun()
        st.caption("Pulled from our Lidl receipts plus what we buy at Tesco/Morrisons/Home Bargains - only adds what isn't already here.")

    with st.expander("Add / update a pantry item"):
        with st.form("add_pantry", clear_on_submit=True):
            name = st.text_input("Item name")
            cols = st.columns(2)
            category = cols[0].selectbox("Category", CATEGORIES, key="pantry_category")
            unit = cols[1].selectbox("Unit", UNITS)
            cols2 = st.columns(2)
            current_stock = cols2[0].number_input("Current stock", min_value=0.0, step=1.0, value=1.0)
            threshold = cols2[1].number_input("Low-stock threshold", min_value=0.0, step=1.0, value=1.0)
            preferred_store = st.selectbox("Usually buy this from", STORES)
            submitted = st.form_submit_button("Save")
            if submitted:
                if name.strip():
                    db.add_pantry_item(name, category, unit, current_stock, threshold, preferred_store)
                    st.rerun()
                else:
                    st.warning("Give the item a name first.")

    st.subheader("All pantry items")
    items = db.get_pantry_items()
    if not items:
        st.info("No pantry items tracked yet - add your regular staples above, or load our usual items.")
    else:
        by_category = {}
        for item in items:
            by_category.setdefault(item["category"], []).append(item)

        for category in CATEGORIES:
            if category not in by_category:
                continue
            with st.expander(f"{category} ({len(by_category[category])})", expanded=False):
                for item in by_category[category]:
                    c1, c2, c3, c4, c5 = st.columns([2.1, 1, 0.5, 0.5, 0.5])
                    label = f"**{item['name']}**"
                    if item["preferred_store"]:
                        label += f"  ·  _{item['preferred_store']}_"
                    c1.markdown(label)
                    c2.markdown(f"{item['current_stock']:g} {item['unit']}")
                    if c3.button("➖", key=f"dec_{item['id']}"):
                        db.adjust_pantry_stock(item["id"], -1)
                        st.rerun()
                    if c4.button("➕", key=f"inc_{item['id']}"):
                        db.adjust_pantry_stock(item["id"], 1)
                        st.rerun()
                    if c5.button("🗑", key=f"del_pantry_{item['id']}"):
                        db.delete_pantry_item(item["id"])
                        st.rerun()


# ---------------------------------------------------------------------------

if page == "🛒 Shopping List":
    render_shopping_list()
elif page == "✅ Household Tasks":
    render_tasks()
else:
    render_stock()
