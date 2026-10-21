# Business Analytics Dashboard Requirements

## Database

`base/input/business_analytics.sqlite` contains three tables:

- `customers(customer_id, customer_name, signup_date, device, channel, country)`
- `orders(order_id, customer_id, order_date, status, amount, category, device, channel)`
- `events(event_id, customer_id, event_type, event_date)`

## Global Rules

- Revenue and order metrics include only orders with `status = 'completed'`.
- Round all monetary values and rates to 2 decimal places.
- `conversion_rate` is a percentage in the range 0-100.
- `monthly_revenue` covers every month from the earliest to the latest `order_date` in `orders`,
  inclusive; months with no completed revenue are `0.00`.
- `revenue_by_category` includes every category that appears in at least one completed order.
- `orders_by_device` and `orders_by_channel` include every value that appears in at least one
  completed order.
- `event_funnel` counts distinct customers per event type. The `purchase` stage is the number of
  distinct customers with at least one completed order.
- `top_10_customers` uses completed orders only. Sort by `total_spend` descending, then
  `customer_id` ascending; return exactly 10 objects with `customer_id`, `customer_name`, and
  `total_spend`.

## Required Metrics

1. `total_revenue`: sum of `amount` over completed orders.
2. `average_order_value`: `total_revenue / total_completed_orders`.
3. `conversion_rate`: distinct purchasing customers / total customers * 100.
4. `total_completed_orders`: count of completed orders.
5. `unique_purchasing_customers`: distinct customers with at least one completed order.
6. `revenue_by_category`: mapping category -> completed revenue.
7. `monthly_revenue`: mapping `YYYY-MM` -> completed revenue, zero-filled across the full month
   range.
8. `orders_by_device`: mapping order device -> completed order count.
9. `orders_by_channel`: mapping order channel -> completed order count.
10. `event_funnel`: mapping event stage (`view`, `add_to_cart`, `checkout`, `purchase`) to distinct
    customer count.
11. `top_10_customers`: ordered list of the top 10 customers by completed spend.

## Output

Write `base/output/dashboard_metrics.json` conforming to `base/input/output_schema.json`.
