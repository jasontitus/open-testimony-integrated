Mobile app features to add 

Upload from gallery.  You should be able to choose one or more photos or videos in your gallery to upload and they should each be fingerprinted (both content and metadata (exif, timestamp, gps, etc)) and uploaded.  They should be marked as signed but not verified at creation time.  This means it really did come from that user's phone and has not been modified afterwards, but it is less verified than if the app had recorded and signed things as it was created.

You should be able to go into the gallery and add info to the uploaded videos which would be uploaded as well (and logged on the server when it was added).  Not signed and managed like the content and original metadata but as a record about the item.  Things like - interview or incident, location info (if it was not provided), and a free form text box.  This can be updated later and only changed by the uploader or an admin on the server side.

Try again to get a more solid signing at creation time using whatever the native tools are for ios or Android to say 'signed by this device at this time'.  The goal is to have a chain of trust that could be submitted in court as safe evidence.

We should also look at how we could implement something server side that logs each thing as it is uploaded so that we have a block chain like log that shows that things truly came in at that time and have not been modified since (on the content and original metadata)
