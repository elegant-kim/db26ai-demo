
-- ONNX 모델 DB에 로드
DECLARE
  ONNX_MOD_FILE VARCHAR2(100) := 'multilingual_e5_small.onnx';
--   ONNX_MOD_FILE VARCHAR2(100) := 'multi_MiniLM_L12_v2.onnx';
--   ONNX_MOD_FILE VARCHAR2(100) := 'all_MiniLM_L12_v2.onnx';
  MODNAME VARCHAR2(500);
  LOCATION_URI VARCHAR2(200) := 'https://adwc4pm.objectstorage.us-ashburn-1.oci.customer-oci.com/p/J7h8Bo3aoIjgHx8WiBRANi2nd3BNpAMx4v33nVnDhU6mIdrhE57hwpNZfupYAS9L/n/adwc4pm/b/OML-ai-models/o/';

BEGIN
  DBMS_OUTPUT.PUT_LINE('ONNX model file name in Object Storage is: '||ONNX_MOD_FILE);
--------------------------------------------
-- 로드된 모델의 모델 이름을 정의합니다
--------------------------------------------

  SELECT UPPER(REGEXP_SUBSTR(ONNX_MOD_FILE, '[^.]+')) INTO MODNAME from dual;
  DBMS_OUTPUT.PUT_LINE('Model will be loaded and saved with name: '||MODNAME);

----------------------------------------------------
-- 객체 스토리지에서 ONNX 모델 파일을 읽어
-- 자율 데이터베이스 데이터 펌프 디렉터리 로 이동
-----------------------------------------------------

BEGIN DBMS_DATA_MINING.DROP_MODEL(model_name => MODNAME);
 EXCEPTION WHEN OTHERS THEN NULL; END;

    DBMS_CLOUD.GET_OBJECT(
      credential_name => NULL,
      directory_name => 'DATA_PUMP_DIR',
      object_uri => LOCATION_URI||ONNX_MOD_FILE);

-----------------------------------------
-- ONNX 모델을 데이터베이스에 로드합니다
-----------------------------------------                   

    DBMS_VECTOR.LOAD_ONNX_MODEL(
      directory => 'DATA_PUMP_DIR',
      file_name => ONNX_MOD_FILE,
      model_name => MODNAME);

    DBMS_OUTPUT.PUT_LINE('New model successfully loaded with name: '||MODNAME);
END;



