-- 013: replace district-name placeholders with actual localities.
-- Safe to run repeatedly; existing real localities are retained.
BEGIN;

DELETE FROM public.location_areas a
USING public.location_districts d
WHERE a.district_id = d.id
  AND lower(trim(a.name)) = lower(trim(d.name));

WITH locality_data(district_name, area_name) AS (
    VALUES
    ('Chennai','Adyar'),('Chennai','Anna Nagar'),('Chennai','T. Nagar'),('Chennai','Velachery'),('Chennai','Tambaram'),('Chennai','Porur'),('Chennai','Guindy'),('Chennai','Sholinganallur'),
    ('Coimbatore','Gandhipuram'),('Coimbatore','RS Puram'),('Coimbatore','Peelamedu'),('Coimbatore','Saibaba Colony'),('Coimbatore','Singanallur'),('Coimbatore','Saravanampatti'),('Coimbatore','Vadavalli'),('Coimbatore','Kuniyamuthur'),('Coimbatore','Town Hall'),('Coimbatore','Ukkadam'),('Coimbatore','Thudiyalur'),
    ('Tiruppur','Avinashi Road'),('Tiruppur','Kangeyam Road'),('Tiruppur','Palladam Road'),('Tiruppur','Dharapuram Road'),('Tiruppur','Anupparpalayam'),
    ('Madurai','Anna Nagar'),('Madurai','KK Nagar'),('Madurai','Tallakulam'),('Madurai','Thirunagar'),('Madurai','Mattuthavani'),('Madurai','Goripalayam'),
    ('Salem','Fairlands'),('Salem','Hasthampatti'),('Salem','Ammapet'),('Salem','Suramangalam'),('Salem','Five Roads'),
    ('Erode','Perundurai Road'),('Erode','Thindal'),('Erode','Solar'),('Erode','Veerappanchatram'),
    ('Tiruchirappalli','Srirangam'),('Tiruchirappalli','Thillai Nagar'),('Tiruchirappalli','Cantonment'),('Tiruchirappalli','KK Nagar'),('Tiruchirappalli','Woraiyur'),
    ('Tirunelveli','Palayamkottai'),('Tirunelveli','Vannarpettai'),('Tirunelveli','Tirunelveli Junction'),('Tirunelveli','Maharaja Nagar'),
    ('Thoothukudi','Millerpuram'),('Thoothukudi','Bryant Nagar'),('Thoothukudi','Beach Road'),
    ('Vellore','Katpadi'),('Vellore','Sathuvachari'),('Vellore','Gandhi Nagar'),('Vellore','Bagayam'),
    ('Dindigul','Nagal Nagar'),('Dindigul','Begampur'),('Dindigul','RM Colony'),
    ('Thanjavur','Medical College Road'),('Thanjavur','New Bus Stand'),('Thanjavur','Karanthai'),
    ('Kancheepuram','Pillaiyarpalayam'),('Kancheepuram','Enathur'),('Kancheepuram','Orikkai'),
    ('Chengalpattu','Maraimalai Nagar'),('Chengalpattu','Guduvanchery'),('Chengalpattu','Singaperumal Koil'),
    ('Tiruvallur','Avadi'),('Tiruvallur','Poonamallee'),('Tiruvallur','Tiruninravur'),
    ('Krishnagiri','Hosur'),('Krishnagiri','Bargur'),('Krishnagiri','Kaveripattinam'),
    ('Namakkal','Tiruchengode'),('Namakkal','Rasipuram'),('Namakkal','Paramathi Velur'),
    ('Karur','Thanthonimalai'),('Karur','Vengamedu'),('Karur','Pasupathipalayam'),
    ('Cuddalore','Nellikuppam'),('Cuddalore','Chidambaram'),('Cuddalore','Panruti'),
    ('Nagapattinam','Velankanni'),('Nagapattinam','Sirkazhi'),('Nagapattinam','Vedaranyam'),
    ('Mayiladuthurai','Sirkazhi'),('Mayiladuthurai','Kuthalam'),('Mayiladuthurai','Tharangambadi'),
    ('Kanniyakumari','Nagercoil'),('Kanniyakumari','Marthandam'),('Kanniyakumari','Colachel'),
    ('Ramanathapuram','Paramakudi'),('Ramanathapuram','Rameswaram'),('Ramanathapuram','Kamalakudi'),
    ('Sivaganga','Karaikudi'),('Sivaganga','Devakottai'),('Sivaganga','Manamadurai'),
    ('Virudhunagar','Sivakasi'),('Virudhunagar','Rajapalayam'),('Virudhunagar','Aruppukkottai'),
    ('Theni','Periyakulam'),('Theni','Bodinayakanur'),('Theni','Cumbum'),
    ('Tenkasi','Sankarankovil'),('Tenkasi','Courtallam'),('Tenkasi','Kadayanallur'),
    ('Pudukkottai','Aranthangi'),('Pudukkottai','Alangudi'),('Pudukkottai','Keeranur'),
    ('Ariyalur','Jayankondam'),('Ariyalur','Sendurai'),
    ('Perambalur','Veppanthattai'),('Perambalur','Kunnam'),
    ('Dharmapuri','Harur'),('Dharmapuri','Palacode'),('Dharmapuri','Pennagaram'),
    ('Nilgiris','Ooty'),('Nilgiris','Coonoor'),('Nilgiris','Kotagiri'),('Nilgiris','Gudalur'),
    ('Tiruvannamalai','Arani'),('Tiruvannamalai','Polur'),('Tiruvannamalai','Chengam'),
    ('Viluppuram','Tindivanam'),('Viluppuram','Gingee'),('Viluppuram','Vikravandi'),
    ('Kallakurichi','Chinnasalem'),('Kallakurichi','Sankarapuram'),('Kallakurichi','Ulundurpet'),
    ('Ranipet','Arcot'),('Ranipet','Arakkonam'),('Ranipet','Walajapet'),
    ('Tirupathur','Vaniyambadi'),('Tirupathur','Ambur'),('Tirupathur','Natrampalli'),
    ('Tiruvarur','Mannargudi'),('Tiruvarur','Thiruthuraipoondi'),('Tiruvarur','Needamangalam')
)
INSERT INTO public.location_areas (district_id, name, is_active)
SELECT d.id, l.area_name, TRUE
FROM locality_data l
JOIN public.location_districts d
  ON lower(d.name) = lower(l.district_name)
JOIN public.location_states s
  ON s.id = d.state_id AND lower(s.name) = 'tamil nadu'
WHERE NOT EXISTS (
    SELECT 1 FROM public.location_areas existing
    WHERE existing.district_id = d.id
      AND lower(existing.name) = lower(l.area_name)
);

COMMIT;
