"""
Vendor Lookup Tool — queries the vendor_master SQLite table.
Supports both exact ID lookup and fuzzy name search.
"""
import json
from agents import function_tool

from database import queries


@function_tool
def vendor_lookup(vendor_name: str = "", vendor_id: str = "") -> str:
    """
    Look up a vendor in the vendor master database.

    Searches by vendor name (fuzzy/partial match) or exact vendor_id.
    Returns vendor details including status (active/inactive/blocked),
    payment terms, and bank account info.

    Use this to validate that an invoice's vendor exists in our system
    and is in good standing before proceeding with approval.

    Args:
        vendor_name: Partial or full vendor name to search for (case-insensitive).
        vendor_id: Exact vendor ID (e.g., "V001") for precise lookup.

    Returns:
        JSON string with vendor details or a not-found message with suggestions.
    """
    if vendor_id:
        result = queries.get_vendor_by_id(vendor_id)
        if result:
            return json.dumps({"found": True, "vendor": result})
        # Fall through to name search if ID not found
        return json.dumps({
            "found": False,
            "message": f"No vendor found with ID '{vendor_id}'",
            "suggestions": [],
        })

    if vendor_name:
        results = queries.search_vendors_by_name(vendor_name)
        if results:
            return json.dumps({
                "found": True,
                "count": len(results),
                "vendors": results,
            })

        # Try broader search with first word
        first_word = vendor_name.split()[0] if vendor_name.split() else vendor_name
        broader = queries.search_vendors_by_name(first_word)
        return json.dumps({
            "found": False,
            "message": f"No vendor found matching '{vendor_name}'",
            "suggestions": broader[:3],
        })

    return json.dumps({
        "found": False,
        "message": "Please provide either vendor_name or vendor_id",
    })
