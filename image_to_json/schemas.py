"""
*date:
hour:
Type of document: (invoice,receipt )
(model)customer:
    *customer id:
    customer name:
    customer phone:
    customer address:
סימוכין:
*invoice number:
table:
    (model)product:
        *product number:
        product name:
        quantity:
        price for unit:
        *total price for product:
payment date:
total price before rounding:
rounding:
total before VAT:
VAT:
*total payment:
name of good receiver:
signature of receiver:
"""
from decimal import Decimal, InvalidOperation
from typing import Annotated,Any
from pydantic import BaseModel,BeforeValidator,Field
from datetime import date, datetime
from enum import StrEnum
def parse_prices(price:str | int | Decimal | float) -> Decimal:
    if price is None or isinstance(price,Decimal):
        return price
    if isinstance(price,(int,float)):
        return Decimal(str(price))
    try:
        return Decimal(str(price).strip().translate((str.maketrans('', '', ',$₪'))))
    except InvalidOperation:
        raise ValueError(f"invalid price: {price!r}")

def parse_dates_formats(value: Any) -> date:
    if isinstance(value,(date,datetime)):
        return value
    if isinstance(value,str):
        formats = [
            "%d.%m.%y",
            "%d/%m/%y",
            "%d/%m/%Y",
            "%d.%m.%Y",
            "%Y-%m-%d",
        ]
        for frmt in formats:
            try:
                return datetime.strptime(value,frmt).date()
            except ValueError:
                continue
    return value

FlexibleDate = Annotated[date,BeforeValidator(parse_dates_formats)]
CleanPrice = Annotated[Decimal,BeforeValidator(parse_prices)]

class DocumentType(StrEnum):
    INVOICE = "חשבונית"
    RECEIPT = "קבלה"
    PAYMENT_DEMAND = "דרישת תשלום"

class Party(BaseModel):
    id: str | None = Field(None, description="id number of party,usually written before:'ת.ז' or 'ח.פ' or 'עוסק פטור' or 'עוסק מורשה'. for the customer, a customer number ('מספר לקוח') also counts as id")
    name: str | None = None
    phone: str | None = None
    address: str | None = None

class Product(BaseModel):
    id: str | None = None
    name: str | None = None
    quantity: Decimal | None = None
    price_for_unit: CleanPrice | None = None
    discount: CleanPrice | None = Field(None,description="Discount, usually written under the column 'הנחה'. this is a discount for a specific item, unlike other discount that is for the entire product. null when the discount is 0.")
    product_total_price: CleanPrice | None

class Invoice(BaseModel):
    date: FlexibleDate | None = None
    hour: str | None = None
    type_of_doc:DocumentType | None = None
    id: str | None
    products: list[Product]| None
    price_before_rounding: CleanPrice | None
    rounding: CleanPrice | None
    price_before_VAT: CleanPrice | None
    vat_amount: CleanPrice | None
    discount: CleanPrice | None = Field(None, description="Discount on whole invoice, near the totals. null when the discount is 0.")
    total_price: CleanPrice | None
    supplier: Party | None = Field(None, description="business that issued the invoice, usually in the header/logo area")
    customer: Party | None = Field(None, description="the billed party, usually after 'לכבוד'")

