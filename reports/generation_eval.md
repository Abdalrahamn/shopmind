# Generation evaluation (Phase 3)

10 questions: 7 answerable, 3 that the documents cannot answer. Retrieval is the Phase 2 default (rewrite + hybrid), 6 chunks, temperature 0.

## Model comparison

| Model | Answered | Facts correct | Refusals correct | Cites only relevant docs | Cites a relevant doc | Made-up citations | Reply in customer's language | Avg latency | Avg tokens in / out |
|---|---|---|---|---|---|---|---|---|---|
| deepseek/deepseek-v4.1-flash | 10/10 | 10/10 | 10/10 | 7/7 | 7/7 | 0 | 10/10 | 3.4 s | 733 / 598 |
| deepseek/deepseek-v4-flash | 10/10 | 7/10 | 10/10 | 7/7 | 7/7 | 0 | 2/10 | 1.3 s | 749 / 153 |

## Problems found

- **deepseek/deepseek-v4-flash**, g01 (policy): wrong language. Answer: "إذا كان المنتج مفتوحًا وفي حالة ممتازة، عندك 14 يوم من تاريخ الاستلام لترجعه، بشرط يكون معاه كل الملحقات والكتالوج والتغليف الأصلي [POL-001]. لو المنتج فيه عيب ووقف شغل خلال أول 30 يوم، تقدر ترجعه حتى لو مفتوح [POL-001]."
- **deepseek/deepseek-v4-flash**, g02 (policy): wrong language. Answer: "التوصيل للإسكندرية: الشحن العادي (Standard) بـ 75 جنيه [POL-002]، والتوصيل السريع (Express) بـ 120 جنيه [POL-002]. مدة التوصيل العادي من 2 لـ 4 أيام عمل، والتوصيل السريع بيوصل اليوم التالي [POL-002]. لو الطلب كبير (زي تل"
- **deepseek/deepseek-v4-flash**, g03 (policy): wrong language. Answer: "تقدر تدفع على 6 شهور بدون فوائد لو استخدمت بطاقة من البنوك الشريكة: CIB، بنك مصر، البنك الأهلي المصري، أو QNB. العرض ده متاح للطلبات اللي قيمتها 3000 جنيه أو أكثر [POL-005]. هتختار خطة التقسيط من صفحة الدفع، والبنك بيحول"
- **deepseek/deepseek-v4-flash**, g04 (multi-doc): wrong or missing fact, wrong language. Answer: "للأسف، Google Pixel 10a من منتجات التصفية (Clearance) وده معناه إنه بيع نهائي ومش ممكن ترجعه إلا لو كان فيه عيب صناعة [POL-001]. لو ظهر عيب خلال أول 30 يوم من الاستلام، تقدر تطلبه استبدال أو استرداد كامل [POL-001]. لو مح"
- **deepseek/deepseek-v4-flash**, g06 (arabic): wrong or missing fact. Answer: "مصاريف الشحن حسب منطقتك وقيمة الطلب: لو طلبك ٢٠٠٠ جنيه أو أكتر والتوصيل للقاهرة أو الجيزة، الشحن مجاناً [POL-002]. لو أقل من كده، الشحن ٥٠ جنيه للقاهرة والجيزة [POL-002]. لباقي المحافظات، الشحن ٧٥ جنيه، وبيبقى مجاناً لو "
- **deepseek/deepseek-v4-flash**, g07 (archived trap): wrong language. Answer: "المبالغ المستردة للبطاقات تستغرق من **5 إلى 10 أيام عمل** بعد استلامنا وفحص المنتج [POL-001]."
- **deepseek/deepseek-v4-flash**, g08 (unanswerable): wrong or missing fact, wrong language. Answer: "مع الأسف، المعلومات المتوفرة عندي مش بتشمل سعر iPhone 17 Pro Max. اللي موجود هو سعر iPhone 17 العادي بـ 57,999 جنيه [SM-PH-003]. لو عايز تفاصيل أكتر، يرجى التواصل مع الدعم الفني على 19555."
- **deepseek/deepseek-v4-flash**, g09 (unanswerable): wrong language. Answer: "معنديش معلومات عن تكلفة إصلاح الشاشة بره الضمان. لو عايز تفاصيل أكتر، اتصل بخدمة العملاء على 19555."
- **deepseek/deepseek-v4-flash**, g10 (unanswerable): wrong language. Answer: "مع الأسف، المعلومات دي مش موجودة عندي. لو عايز تعرف مين الرئيس التنفيذي لـ ShopMind، ممكن تتصل بخدمة العملاء على 19555."

## Answers

**g01 (policy): how many days do I have to return a product I already opened?**

- `deepseek/deepseek-v4.1-flash` (answered; cites POL-001): If you opened the product and it is in perfect condition, you have 14 days from delivery to return it, and it must include all original accessories, manuals, and packaging [POL-001]. If the product is defective, it can be replaced or refunded in full within the first 30 days, whether it was opened or not [POL-001].
- `deepseek/deepseek-v4-flash` (answered; cites POL-001): إذا كان المنتج مفتوحًا وفي حالة ممتازة، عندك 14 يوم من تاريخ الاستلام لترجعه، بشرط يكون معاه كل الملحقات والكتالوج والتغليف الأصلي [POL-001]. لو المنتج فيه عيب ووقف شغل خلال أول 30 يوم، تقدر ترجعه حتى لو مفتوح [POL-001].

**g02 (policy): how much is delivery to Alexandria?**

- `deepseek/deepseek-v4.1-flash` (answered; cites POL-002): Standard shipping to Alexandria is 75 EGP, and it's free on orders of 5,000 EGP or more [POL-002]. If you need it faster, express delivery is 120 EGP and arrives the next business day [POL-002]. Standard delivery to Alexandria takes 2 to 4 business days [POL-002].
- `deepseek/deepseek-v4-flash` (answered; cites POL-002): التوصيل للإسكندرية: الشحن العادي (Standard) بـ 75 جنيه [POL-002]، والتوصيل السريع (Express) بـ 120 جنيه [POL-002]. مدة التوصيل العادي من 2 لـ 4 أيام عمل، والتوصيل السريع بيوصل اليوم التالي [POL-002]. لو الطلب كبير (زي تلفزيون أكبر من 55 بوصة أو كرسي جيمنج) برا القاهرة والجيزة، فيه رسوم ثابتة 150 جنيه [POL-002].

**g03 (policy): pay over 6 months with no interest**

- `deepseek/deepseek-v4.1-flash` (answered; cites POL-005): Yes — 0% interest for 6 months is available with cards from partner banks: CIB, Banque Misr, National Bank of Egypt, and QNB. It applies to orders of 3,000 EGP or more. You choose the instalment plan on the payment page, and your bank converts the purchase within one billing cycle. [POL-005]
- `deepseek/deepseek-v4-flash` (answered; cites POL-005): تقدر تدفع على 6 شهور بدون فوائد لو استخدمت بطاقة من البنوك الشريكة: CIB، بنك مصر، البنك الأهلي المصري، أو QNB. العرض ده متاح للطلبات اللي قيمتها 3000 جنيه أو أكثر [POL-005]. هتختار خطة التقسيط من صفحة الدفع، والبنك بيحول المبلغ خلال دورة الفوترة الأولى [POL-005].

**g04 (multi-doc): can I return the Pixel 10a?**

- `deepseek/deepseek-v4.1-flash` (answered; cites SM-PH-005, POL-001): The Pixel 10a is a clearance item marked final sale [SM-PH-005]. Clearance items cannot be returned unless they are defective [POL-001]. So if it is not defective, you cannot return it. If it is defective and stops working within the first 30 days, it can be replaced or refunded in full [POL-001].
- `deepseek/deepseek-v4-flash` (answered; cites POL-001, SM-PH-005): للأسف، Google Pixel 10a من منتجات التصفية (Clearance) وده معناه إنه بيع نهائي ومش ممكن ترجعه إلا لو كان فيه عيب صناعة [POL-001]. لو ظهر عيب خلال أول 30 يوم من الاستلام، تقدر تطلبه استبدال أو استرداد كامل [POL-001]. لو محتاج مساعدة أكتر، اتصل بخدمة العملاء على 19555.

**g05 (arabic): ازاي ارجع منتج فتحته؟**

- `deepseek/deepseek-v4.1-flash` (answered; cites POL-001): لو المنتج مفتوح وفي حالة ممتازة، تقدر ترجعه خلال 14 يوم من التوصيل، ولازم يكون معاه كل الملحقات والكتيبات والتغليف الأصلي [POL-001].

طريقة الإرجاع:
1. افتح My Orders في حسابك واختر الطلب [POL-001].
2. اختر Request Return وحدد المنتجات والسبب [POL-001].
3. فريقنا يراجع الطلب خلال 2 أيام عمل [POL-001].
4. بعد الموافقة، المندوب يستلم المنتج من عنوانك مجانًا في القاهرة والجيزة، أو تقدر تسلمه في أي فرع ShopMind [POL-001].

ملاحظة: لو المنتج فيه عيب، خلال أول 30 يوم نستبدله أو نرجّع قيمته كاملة حتى لو مفتوح [POL-001]. وفي منتجات مفتوحة ماينفعش ترجع: السوفت وير المفتوح، بطاقات الهدايا، الأكواد الرقمية، سماعات الأذن/الإيربودز بعد كسر الختم الصحي إلا لو فيها عيب، ومنتجات Clearance نهائية إلا لو فيها عيب [POL-001].
- `deepseek/deepseek-v4-flash` (answered; cites POL-001): لو المنتج اللي فتحته في حالة كويسة و معاه كل محتوياته، تقدر ترجعه خلال 14 يوم من الاستلام [POL-001]. عشان تبدأ الطلب، افتح My Orders في حسابك، اختار الطلب، واضغط Request Return، واختار المنتج وسبب الإرجاع. الفريق هيراجع طلبك خلال 2 يوم عمل، وبعدها هتستلم المنتج منك مجانًا لو في القاهرة أو الجيزة، أو تقدر تسيبه في أي فرع من ShopMind [POL-001].

**g06 (arabic): مصاريف الشحن كام؟**

- `deepseek/deepseek-v4.1-flash` (answered; cites POL-002): أهلاً بيك! دي مصاريف الشحن عندنا:

• القاهرة والجيزة: الشحن العادي مجاني للطلبات 2,000 جنيه أو أكثر، ولو أقل من كده بـ 50 جنيه [POL-002].
• باقي المحافظات: الشحن العادي بـ 75 جنيه، ومجاني للطلبات 5,000 جنيه أو أكثر [POL-002].
• الشحن السريع بـ 120 جنيه، ومش مجاني أبداً [POL-002].
• الأجهزة الكبيرة زي التلفزيونات فوق 55 بوصة والكراسي الجيمنج: رسوم ثابتة 150 جنيه بره القاهرة والجيزة [POL-002].

لو حابب تعرف تفاصيل أكتر، كلمنا على 19555.
- `deepseek/deepseek-v4-flash` (answered; cites POL-002): مصاريف الشحن حسب منطقتك وقيمة الطلب: لو طلبك ٢٠٠٠ جنيه أو أكتر والتوصيل للقاهرة أو الجيزة، الشحن مجاناً [POL-002]. لو أقل من كده، الشحن ٥٠ جنيه للقاهرة والجيزة [POL-002]. لباقي المحافظات، الشحن ٧٥ جنيه، وبيبقى مجاناً لو الطلب ٥٠٠٠ جنيه أو أكتر [POL-002]. التوصيل السريع بـ ١٢٠ جنيه ومش بيكون مجاني أبداً [POL-002]. الأغراض الكبيرة زي تلفزيونات فوق ٥٥ بوصة أو كراسي جيمنج، عليهم رسوم ثابتة ١٥٠ جنيه بره القاهرة والجيزة [POL-002].

**g07 (archived trap): how long do card refunds take?**
*The archived 2024 policy says 14 business days; the current one says 5 to 10.*

- `deepseek/deepseek-v4.1-flash` (answered; cites POL-001, FAQ-006): Card refunds take **5 to 10 business days** after we receive and inspect the returned item [POL-001][FAQ-006].
- `deepseek/deepseek-v4-flash` (answered; cites POL-001): المبالغ المستردة للبطاقات تستغرق من **5 إلى 10 أيام عمل** بعد استلامنا وفحص المنتج [POL-001].

**g08 (unanswerable): what is the price of the iPhone 17 Pro Max?**
*Only the iPhone 17 is in the catalogue. Its price must not be given as the Pro Max price.*

- `deepseek/deepseek-v4.1-flash` (said it does not know; cites nothing): I don’t have information about the iPhone 17 Pro Max price. Please contact support on 19555 for help.
- `deepseek/deepseek-v4-flash` (said it does not know; cites SM-PH-003): مع الأسف، المعلومات المتوفرة عندي مش بتشمل سعر iPhone 17 Pro Max. اللي موجود هو سعر iPhone 17 العادي بـ 57,999 جنيه [SM-PH-003]. لو عايز تفاصيل أكتر، يرجى التواصل مع الدعم الفني على 19555.

**g09 (unanswerable): how much does a screen repair cost outside the warranty?**

- `deepseek/deepseek-v4.1-flash` (said it does not know; cites POL-003): I don’t have the screen repair cost outside warranty in my sources. The standard warranty doesn’t cover cracked screens [POL-003]. Please contact support on 19555 for a repair quote.
- `deepseek/deepseek-v4-flash` (said it does not know; cites nothing): معنديش معلومات عن تكلفة إصلاح الشاشة بره الضمان. لو عايز تفاصيل أكتر، اتصل بخدمة العملاء على 19555.

**g10 (unanswerable): who is the CEO of ShopMind?**

- `deepseek/deepseek-v4.1-flash` (said it does not know; cites nothing): I don’t have this information. Please contact support on 19555.
- `deepseek/deepseek-v4-flash` (said it does not know; cites nothing): مع الأسف، المعلومات دي مش موجودة عندي. لو عايز تعرف مين الرئيس التنفيذي لـ ShopMind، ممكن تتصل بخدمة العملاء على 19555.

## Sampling: temperature 0 vs high temperature

Question: *can I return the Pixel 10a?* asked 3 times per temperature with `deepseek/deepseek-v4.1-flash`.

**Temperature 0.0:** 3 different wordings in 3 runs, 48–52 words, key fact correct in 3/3.

1. The Pixel 10a is a clearance item marked final sale [SM-PH-005]. Clearance items cannot be returned unless they are defective [POL-001]. So if it is not defective, you cannot return it. If it is defective and stops working within the first 30 days, it can be replaced or refunded in full [POL-001].
2. Unfortunately, the Google Pixel 10a is a clearance item and final sale, so it cannot be returned unless it is defective [SM-PH-005] [POL-001]. If it is defective within the first 30 days, it can be replaced or fully refunded [POL-001]. After 30 days, defects are handled under the warranty policy [POL-001].
3. The Pixel 10a is a clearance item and final sale, so it can’t be returned for change of mind [SM-PH-005][POL-001]. If it’s defective, you can get a replacement or full refund within 30 days of delivery [POL-001]. After 30 days, defects are handled under the 12-month warranty [POL-001][SM-PH-005].

**Temperature 1.5:** 3 different wordings in 3 runs, 46–58 words, key fact correct in 3/3.

1. The Pixel 10a is a clearance item and is final sale [SM-PH-005]. Clearance items cannot be returned unless they are defective [POL-001]. So you can’t return it just because you changed your mind. If it is defective within the first 30 days, it can be replaced or refunded in full [POL-001].
2. Generally no. The Google Pixel 10a is marked as a clearance item with final sale, so it cannot be returned unless it is defective. If it is defective within the first 30 days, it can be replaced or refunded in full, whether opened or not. [SM-PH-005][POL-001]
3. Unfortunately, the Pixel 10a can't be returned. It's listed as a Clearance item and final sale, and items sold in the Clearance section are final sale and cannot be returned — unless the product is defective. [SM-PH-005][POL-001] So if it arrives defective (stops working within the first 30 days), we'd replace it or refund you in full. [POL-001]

