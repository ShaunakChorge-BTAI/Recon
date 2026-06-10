import { useState } from "react";
import FileUpload from "../components/FileUpload";
import ColumnMapping from "../components/ColumnMapping";

export default function Dashboard() {
  const [uploadData, setUploadData] = useState(null);
  const [uploading, setUploading] = useState(false);

  return (
    <div className="p-6">
      <FileUpload
        onUploadComplete={setUploadData}
        uploading={uploading}
        setUploading={setUploading}
      />

      {uploading && (
        <div className="mt-4 flex items-center gap-3">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
          <span className="text-sm text-gray-600">Uploading and loading columns...</span>
        </div>
      )}

      {!uploading && uploadData && (
        <div className="mt-6">
          <ColumnMapping
            sourceCols={uploadData.source_columns}
            destCols={uploadData.dest_columns}
            sourceUploadId={uploadData.source_upload_id}
            destUploadId={uploadData.dest_upload_id}
          />
        </div>
      )}
    </div>
  );
}