# Agent demo (Phase 4)

Every step below was streamed live while the agent worked.

## 1. A policy question → documents (RAG)

**Khaled Zaki (customer):** how long do I have to return something I opened?

- 🔧 calls `search_store_docs` with `{"query": "return policy opened product"}`
- 📥 `search_store_docs` returned: [POL-001] Return and Refund Policy Return and Refund Policy > Return windows  - **Unopened products:** you can return them within **30 days** of delivery for a full refund. - **Opened products in perfect condition:** you can retur…

**ShopMind:** You can return an opened product within **14 days** of delivery, provided it is in perfect condition and includes all original accessories, manuals, and packaging [POL-001]. 

Please note that certain opened items (like in-ear headphones/earbuds once the hygiene seal is broken, opened software/digital codes, or clearance items) cannot be returned unless they are defective [POL-001]. If the item is defective, you have 30 days from delivery to return or replace it [POL-001].

*route: documents · sources: POL-001 · 6.5 s · answered by gemini-3.6-flash*

## 2. A numbers question from staff → database (SQL)

**Mona (store manager) (staff):** who are our top 5 customers by total spending?

- 🔧 calls `query_database` with `{"sql": "SELECT c.full_name, SUM(o.total_egp) as total_spent\nFROM customers c\nJOIN orders o ON c.customer_id = o.customer_id\nWHERE o.status = 'delivered'\nGROUP BY c.customer_id\nORDER BY total_spent DESC\nLIMIT 5;"}`
- 📥 `query_database` returned: full_name | total_spent Ali Mahfouz | 254993 Yasmin Sherif | 253794 Hassan Sherif | 218493 Mariam Naguib | 204592 Farida Ibrahim | 199266

**ShopMind:** أهلاً يا منى، إليك قائمة بأفضل 5 عملاء لدينا من حيث إجمالي المشتريات (للطلبات التي تم تسليمها):

1. علي محفوظ: 254,993 ج.م
2. ياسمين شريف: 253,794 ج.م
3. حسن شريف: 218,493 ج.م
4. مريم نجيب: 204,592 ج.م
5. فريدة إبراهيم: 199,266 ج.م

*route: database · sources: none · 34.1 s · answered by gemini-3.1-flash-lite*

## 3. The same question from a customer → refused (dynamic prompt + code check)

**Khaled Zaki (customer):** who are your top 5 customers by total spending?

- 🔧 calls `query_database` with `{"sql": "SELECT c.full_name, SUM(o.total_egp) as total_spent\nFROM customers c\nJOIN orders o ON c.customer_id = o.customer_id\nWHERE o.status = 'delivered'\nGROUP BY c.customer_id\nORDER BY total_spent DESC\nLIMIT 5;"}`
- 📥 `query_database` returned: Refused: only staff can query the database. For a customer's own orders use get_my_orders.

**ShopMind:** I'm sorry, but I cannot share information about other customers' spending or personal details due to privacy policies. If you have any questions about your own orders or our products and policies, feel free to ask!

*route: none · sources: none · 2.8 s · answered by gemini-3.6-flash*

## 4. Product advice with a budget and stock → documents + filter + MCP, then memory

**Khaled Zaki (customer):** عايز موبايل تحت 15 الف ويكون متوفر دلوقتي

- 🔧 calls `search_store_docs` with `{"product_category": "phones", "query": "موبايل تحت 15000", "max_price_egp": 15000}`
- 📥 `search_store_docs` returned: [SM-PH-004] Xiaomi Redmi Note 15 Pro Xiaomi Redmi Note 15 Pro > Key specs  - 6.67-inch AMOLED, 120Hz - 256 GB storage, 8 GB RAM - 200 MP main camera - 5,100 mAh battery, 90W charging  [SM-PH-004] Xiaomi Redmi Note 15 Pro Xiaomi Re…
- 🔧 calls `check_stock` with `{"product": "SM-PH-004"}`
- 📥 `check_stock` returned: [{'type': 'text', 'text': '[{"sku": "SM-PH-004", "name": "Xiaomi Redmi Note 15 Pro", "price_egp": 13999, "stock_qty": 18, "in_stock": true}]', 'id': 'lc_9513f43d-2f2f-44dc-b57a-ee60c5eb09b6'}]

**ShopMind:** أهلاً يا خالد، متاح حالياً موبايل Xiaomi Redmi Note 15 Pro بسعر 13,999 جنيه، وهو متوفر في المخزون [SM-PH-004]. الموبايل بيقدم مواصفات ممتازة زي كاميرا 200 ميجابكسل وشحن سريع 90 وات. تحب أساعدك في طلبه؟

*route: mixed · sources: SM-PH-004 · 4.9 s · answered by gemini-3.1-flash-lite*

### Follow-up in the same conversation → memory

**Khaled Zaki (customer):** وضمانه قد ايه؟

- 🔧 calls `search_store_docs` with `{"query": "ضمان Xiaomi Redmi Note 15 Pro", "doc_type": "product"}`
- 📥 `search_store_docs` returned: [SM-PH-004] Xiaomi Redmi Note 15 Pro Xiaomi Redmi Note 15 Pro > Key specs  - 6.67-inch AMOLED, 120Hz - 256 GB storage, 8 GB RAM - 200 MP main camera - 5,100 mAh battery, 90W charging  [SM-PH-004] Xiaomi Redmi Note 15 Pro Xiaomi Re…

**ShopMind:** ضمان موبايل Xiaomi Redmi Note 15 Pro هو 12 شهر [SM-PH-004].

*route: documents · sources: SM-PH-004 · 2.6 s · answered by gemini-3.1-flash-lite*

## 5. Cancel an order → human-in-the-loop

**Khaled Zaki (customer):** please cancel my order 1049

- 🔧 calls `cancel_order` with `{"order_id": 1049}`
- ⏸️ **paused for approval:** `cancel_order` with `{"order_id": 1049}`

While paused, order 1049 is still `pending` in the database. A human now approves.

- 🔧 calls `cancel_order` with `{"order_id": 1049}`
- 📥 `cancel_order` returned: Order 1049 is now cancelled. Prepaid orders are refunded to the original payment method.

**ShopMind:** تم إلغاء طلبك رقم 1049 بنجاح. إذا كنت قد دفعت مسبقاً، فسيتم استرداد المبلغ إلى وسيلة الدفع الأصلية.

*route: action · sources: none · 23.6 s · answered by gemini-3.1-flash-lite*

After approval, order 1049 is `cancelled` in the database.
