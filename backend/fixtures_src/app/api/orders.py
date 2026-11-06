class Order:
    def __init__(self, order_id, customer):
        self.order_id = order_id
        self.customer = customer


def find_order(order_id):
    return Order(order_id, customer=None)


def get_order_owner(order_id):
    order = find_order(order_id)
    return {"order": order.order_id, "owner": order.customer.id}
