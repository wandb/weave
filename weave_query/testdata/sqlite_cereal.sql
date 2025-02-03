PRAGMA foreign_keys=off;

BEGIN TRANSACTION;

ALTER TABLE cereal RENAME TO _cereal_old;


CREATE TABLE cereal(
  "name" TEXT,
  "mfr" TEXT,
  "type" TEXT,
  "calories" INTEGER,
  "protein" INTEGER,
  "fat" INTEGER,
  "sodium" INTEGER,
  "fiber" INTEGER,
  "carbo" REAL,
  "sugars" INTEGER,
  "potass" INTEGER,
  "vitamins" INTEGER,
  "shelf" INTEGER,
  "weight" REAL,
  "cups" REAL,
  "rating" REAL
);

INSERT INTO cereal ("name", "mfr", "type", "calories", "protein", "fat", "sodium", "fiber", "carbo", "sugars", "potass", "vitamins", "shelf", "weight", "cups", "rating")
  SELECT "name", "mfr", "type", "calories", "protein", "fat", "sodium", "fiber", "carbo", "sugars", "potass", "vitamins", "shelf", "weight", "cups", "rating"

  FROM _cereal_old;

COMMIT;

PRAGMA foreign_keys=on;
