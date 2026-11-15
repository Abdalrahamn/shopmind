# Generation evaluation (Phase 3)

10 questions: 7 answerable, 3 that the documents cannot answer. Retrieval is the Phase 2 default (rewrite + hybrid), 6 chunks, temperature 0.

## Model comparison

| Model | Answered | Facts correct | Refusals correct | Cites only relevant docs | Cites a relevant doc | Made-up citations | Reply in customer's language | Avg latency | Avg tokens in / out |
|---|---|---|---|---|---|---|---|---|---|
| gemini-3.5-flash | 10/10 | 10/10 | 10/10 | 7/7 | 7/7 | 0 | 10/10 | 4.2 s | 708 / 739 |
| gemini-3.5-flash-lite | 10/10 | 9/10 | 10/10 | 7/7 | 7/7 | 0 | 5/10 | 1.0 s | 708 / 95 |

## Problems found

- **gemini-3.5-flash-lite**, g03 (policy): wrong language. Answer: "أهلاً بك! يمكنك التقسيط بدون فوائد لمدة 6 أشهر باستخدام بطاقات من البنوك الشريكة (البنك التجاري الدولي CIB، بنك مصر، البنك الأهلي المصري، وقناة السويس QNB)، وذلك للطلبات بقيمة 3000 جنيه مصري أو أكثر [POL-005]."
- **gemini-3.5-flash-lite**, g04 (multi-doc): wrong or missing fact, wrong language. Answer: "أهلاً بك! بالنسبة لجوجل Pixel 10a، فهو منتج تصفية (Clearance) وبالتالي يعتبر بيعاً نهائياً ولا يمكن إرجاعه إلا إذا كان عائباً [SM-PH-005, POL-001]."
- **gemini-3.5-flash-lite**, g08 (unanswerable): wrong language. Answer: "عذراً، لا أملك معلومات عن سعر iPhone 17 Pro Max. يمكنك التواصل معنا على رقم الدعم 19555 لمعرفة المزيد."
- **gemini-3.5-flash-lite**, g09 (unanswerable): wrong language. Answer: "عذراً، لا أملك معلومات حول تكلفة إصلاح الشاشة خارج الضمان. يرجى التواصل مع الدعم على 19555 للمساعدة."
- **gemini-3.5-flash-lite**, g10 (unanswerable): wrong language. Answer: "عذراً، لا أملك هذه المعلومات. يمكنك التواصل مع خدمة العملاء على 19555."

## Answers

**g01 (policy): how many days do I have to return a product I already opened?**

- `gemini-3.5-flash` (answered; cites POL-001, FAQ-005): If you opened the product and it is in perfect condition (with all original accessories, manuals, and packaging), you have 14 days from delivery to return it [POL-001] [FAQ-005]. However, if the opened product is defective, you can return it within 30 days of delivery for a full refund or replacement [POL-001] [FAQ-005].
- `gemini-3.5-flash-lite` (answered; cites POL-001): You have 14 days from delivery to return an opened product in perfect condition with all original accessories, manuals, and packaging [POL-001].

**g02 (policy): how much is delivery to Alexandria?**

- `gemini-3.5-flash` (answered; cites POL-002): Standard shipping to Alexandria is 75 EGP, and it is free for orders of 5,000 EGP or more [POL-002]. Express delivery costs 120 EGP [POL-002]. For large items (such as TVs over 55 inches or gaming chairs), there is a fixed fee of 150 EGP outside Cairo and Giza [POL-002].
- `gemini-3.5-flash-lite` (answered; cites POL-002): Standard shipping to Alexandria (and Delta and Canal cities) is 75 EGP, and it is free on orders of 5,000 EGP or more [POL-002]. Express delivery is next business day and costs 120 EGP (never free) [POL-002].

**g03 (policy): pay over 6 months with no interest**

- `gemini-3.5-flash` (answered; cites POL-005): You can get 0% interest for 6 months using cards from partner banks, which include CIB, Banque Misr, National Bank of Egypt, and QNB [POL-005]. Instalment plans are available for orders of 3,000 EGP or more [POL-005]. You can select the instalment plan on the payment page, and your bank will convert the purchase within one billing cycle [POL-005].
- `gemini-3.5-flash-lite` (answered; cites POL-005): أهلاً بك! يمكنك التقسيط بدون فوائد لمدة 6 أشهر باستخدام بطاقات من البنوك الشريكة (البنك التجاري الدولي CIB، بنك مصر، البنك الأهلي المصري، وقناة السويس QNB)، وذلك للطلبات بقيمة 3000 جنيه مصري أو أكثر [POL-005].

**g04 (multi-doc): can I return the Pixel 10a?**

- `gemini-3.5-flash` (answered; cites SM-PH-005, POL-001): The Google Pixel 10a is a clearance item (final sale) [SM-PH-005], so it cannot be returned unless it is defective [POL-001]. If it is defective within the first 30 days, it can be replaced or fully refunded [POL-001].
- `gemini-3.5-flash-lite` (answered; cites SM-PH-005, POL-001): أهلاً بك! بالنسبة لجوجل Pixel 10a، فهو منتج تصفية (Clearance) وبالتالي يعتبر بيعاً نهائياً ولا يمكن إرجاعه إلا إذا كان عائباً [SM-PH-005, POL-001].

**g05 (arabic): ازاي ارجع منتج فتحته؟**

- `gemini-3.5-flash` (answered; cites POL-001): تقدر ترجع المنتج المفتوح خلال 14 يوم من التوصيل بشرط يكون بحالة ممتازة ومعاه كل الملحقات والكتالوجات والتغليف الأصلي [POL-001]. أما لو المنتج فيه عيب، تقدر ترجعه خلال 30 يوم سواء مفتوح أو لا [POL-001]. (تنبيه: البرامج المفتوحة، وسماعات الأذن إذا تم كسر ختم Hygiene Seal، ومنتجات التصفية Clearance لا يمكن إرجاعها إلا إذا كانت معيبة [POL-001]). لطلب الإرجاع: 1. افتح طلباتي (My Orders) من حسابك واختار الطلب [POL-001]. 2. اختار طلب إرجاع (Request Return) وحدد المنتجات والسبب [POL-001]. 3. بيتم مراجعة الطلب خلال يومين عمل [POL-001]. 4. بعد الموافقة، مندوب بيستلم المنتج مجانًا (في القاهرة والجيزة) أو تقدر تسلمه في أي فرع من فروع ShopMind [POL-001].
- `gemini-3.5-flash-lite` (answered; cites POL-001): عشان ترجع منتج فتحته، لازم يكون في حالة ممتازة ومعاه كل الإكسسوارات الأصلية والكتيبات والعبوة خلال 14 يوم من تاريخ الاستلام [POL-001]. تقدر تبدأ المرتجع من قسم "طلباتي" في حسابك، تختار الطلب وتدوس "طلب إرجاع" وتحدد المنتجات والسبب [POL-001].

**g06 (arabic): مصاريف الشحن كام؟**

- `gemini-3.5-flash` (answered; cites POL-002): مصاريف الشحن بتختلف حسب المكان وحجم الطلب:
- الشحن القياسي للقاهرة والجيزة: 50 جنيه، ومجاناً للطلبات بقيمة 2,000 جنيه أو أكثر [POL-002].
- الشحن القياسي لباقي المحافظات: 75 جنيه، ومجاناً للطلبات بقيمة 5,000 جنيه أو أكثر [POL-002].
- التوصيل السريع (Express): 120 جنيه وغير مجاني تماماً [POL-002].
- المنتجات الكبيرة (تلفزيونات أكبر من 55 بوصة أو كراسي الألعاب): رسوم ثابتة 150 جنيه خارج القاهرة والجيزة [POL-002].
- `gemini-3.5-flash-lite` (answered; cites POL-002): مصاريف الشحن كالتالي:
- الشحنات القياسية للقاهرة والجيزة مجانية للطلبات من 2000 جنيه أو أكثر، وتكون 50 جنيه للطلبات الأصغر [POL-002].
- الشحن القياسي لباقي المحافظات هو 75 جنيه، ومجاني للطلبات من 5000 جنيه أو أكثر [POL-002].
- التوصيل السريع هو 120 جنيه ومش بيبقى مجاني أبداً [POL-002].
- الأجهزة الكبيرة (زي التليفزيونات الأكبر من 55 بوصة وكراسي الألعاب) ليها رسوم ثابتة 150 جنيه بره القاهرة والجيزة [POL-002].

**g07 (archived trap): how long do card refunds take?**
*The archived 2024 policy says 14 business days; the current one says 5 to 10.*

- `gemini-3.5-flash` (answered; cites POL-001, FAQ-006): Card refunds take 5 to 10 business days after we receive and inspect the returned item [POL-001] [FAQ-006].
- `gemini-3.5-flash-lite` (answered; cites POL-001): Card refunds take 5 to 10 business days after we receive and inspect the item [POL-001].

**g08 (unanswerable): what is the price of the iPhone 17 Pro Max?**
*Only the iPhone 17 is in the catalogue. Its price must not be given as the Pro Max price.*

- `gemini-3.5-flash` (said it does not know; cites nothing): I do not have information about the price of the iPhone 17 Pro Max. Please contact our support team on 19555 for assistance.
- `gemini-3.5-flash-lite` (said it does not know; cites nothing): عذراً، لا أملك معلومات عن سعر iPhone 17 Pro Max. يمكنك التواصل معنا على رقم الدعم 19555 لمعرفة المزيد.

**g09 (unanswerable): how much does a screen repair cost outside the warranty?**

- `gemini-3.5-flash` (said it does not know; cites nothing): I am sorry, but I don't have information about the cost of screen repairs outside the warranty. Please contact customer support on 19555 for assistance.
- `gemini-3.5-flash-lite` (said it does not know; cites nothing): عذراً، لا أملك معلومات حول تكلفة إصلاح الشاشة خارج الضمان. يرجى التواصل مع الدعم على 19555 للمساعدة.

**g10 (unanswerable): who is the CEO of ShopMind?**

- `gemini-3.5-flash` (said it does not know; cites nothing): I'm sorry, but I do not have information regarding who the CEO of ShopMind is. Please contact support on 19555 for assistance.
- `gemini-3.5-flash-lite` (said it does not know; cites nothing): عذراً، لا أملك هذه المعلومات. يمكنك التواصل مع خدمة العملاء على 19555.

## Sampling: temperature 0 vs high temperature

Question: *can I return the Pixel 10a?* asked 3 times per temperature with `gemini-3.5-flash`.

**Temperature 0.0:** 3 different wordings in 3 runs, 21–49 words, key fact correct in 3/3.

1. The Google Pixel 10a is a clearance item (final sale) [SM-PH-005], so it cannot be returned unless it is defective [POL-001]. If it is defective within the first 30 days, it can be replaced or fully refunded [POL-001].
2. The Google Pixel 10a is a clearance item (final sale) [SM-PH-005], so it cannot be returned unless it is defective [POL-001].
3. The Google Pixel 10a is a clearance item and marked as final sale [SM-PH-005]. Items sold in the Clearance section cannot be returned unless they are defective [POL-001]. If the product is defective within the first 30 days of delivery, it can be replaced or refunded in full [POL-001].

**Temperature 1.5:** 3 different wordings in 3 runs, 24–42 words, key fact correct in 3/3.

1. The Google Pixel 10a is a clearance item and marked as final sale [SM-PH-005]. Items sold in the clearance section cannot be returned unless they are defective [POL-001].
2. The Google Pixel 10a is a clearance item (final sale) [SM-PH-005], which means it cannot be returned unless it is defective [POL-001]. If it stops working within the first 30 days of delivery, it can be replaced or refunded in full [POL-001].
3. The Google Pixel 10a is a clearance item and marked as final sale [SM-PH-005]. Therefore, it cannot be returned unless it is defective [POL-001].

